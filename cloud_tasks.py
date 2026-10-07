"""Business operations shared by queue workers; no web server or global lock."""
import hashlib, json
import cancellation, learning, ondemand, study, target, tutor
from core import extract
from render import render

def execute(path,payload):
    cancellation.check()
    actions={
        '/api/tutor/answer':lambda:tutor.answer(payload),
        '/api/practice/next':lambda:ondemand.practice(payload),
        '/api/exams/generate':lambda:ondemand.exam(payload),
        '/api/essay/theme':lambda:learning.theme(str(payload.get('context',''))+'\nRubrica: '+json.dumps(learning.rubric(payload.get('exam_index')),ensure_ascii=False),preferred_theme=payload.get('preferred_theme','')),
        '/api/essay/transcribe':lambda:learning.transcribe(payload.get('images')),
        '/api/essay/grade':lambda:learning.grade(payload),
        '/api/board/analyze':lambda:study.board(payload)
    }
    if path in actions:return actions[path](),'application/json'
    if path=='/api/material/pdf':
        data=study.material(payload);cancellation.check();cancellation.set_stage('Montando as páginas do PDF…')
        return study.pdf(data),'application/pdf'
    text=payload.get('text')
    if not isinstance(text,str) or not 80<=len(text)<=5000000:raise ValueError('Texto do edital inválido ou sem conteúdo suficiente.')
    if path=='/api/target/analyze':return {'target':target.analyze(text,payload.get('source','Edital'))},'application/json'
    if path=='/api/guide':
        summary=extract(text);stored=target.read();digest=hashlib.sha256(b'target-schema-v2\n'+text.encode()).hexdigest()
        return render(summary,stored if stored and stored.get('digest')==digest else None),'application/pdf'
    raise ValueError('Operação de geração inválida.')

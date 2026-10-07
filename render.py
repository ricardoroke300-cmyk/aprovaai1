"""Professional edital guide with comfortable type and a full vertical syllabus."""
from io import BytesIO
from xml.sax.saxutils import escape
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet,ParagraphStyle
from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer,Table,TableStyle,KeepTogether,Flowable,PageBreak,CondPageBreak
from core import validate
WIDTH=A4[0]-88
NAVY=colors.HexColor('#132C4C');BLUE=colors.HexColor('#1764BC');INK=colors.HexColor('#102033')
ACCENTS={'calendar':'#E86716','money':'#147B43','people':'#8C3BA8','clock':'#0F827F','pin':'#C83868','case':'#2563B5','book':'#7B3AAF','check':'#14804B','shield':'#B8432F'}

class Icon(Flowable):
    def __init__(self,kind,size=44):super().__init__();self.kind=kind;self.width=self.height=size
    def draw(self):
        c=self.canv;s=self.width;c.saveState();c.translate(s/2,s/2);c.scale(s/44,s/44)
        color=colors.HexColor(ACCENTS.get(self.kind,'#1764BC'));c.setFillColor(color);c.circle(0,0,20,fill=1,stroke=0)
        c.setStrokeColor(colors.white);c.setFillColor(colors.white);c.setLineWidth(1.8);k=self.kind
        if k=='calendar':
            c.roundRect(-10,-10,20,19,2,fill=0,stroke=1);c.line(-10,3,10,3);c.line(-5,12,-5,6);c.line(5,12,5,6)
            for x in (-5,0,5):
                for y in (-2,-6):c.circle(x,y,.9,fill=1,stroke=0)
        elif k=='money':
            c.roundRect(-12,-8,24,16,2,fill=0,stroke=1);c.circle(0,0,5,fill=0,stroke=1);c.setFont('Helvetica-Bold',9);c.drawCentredString(0,-3,'$');c.line(-8,-2,-8,2);c.line(8,-2,8,2)
        elif k=='people':
            for x,y,r in ((0,5,4),(-10,3,3),(10,3,3)):c.circle(x,y,r,fill=0,stroke=1)
            c.roundRect(-6,-10,12,9,3,fill=0,stroke=1);c.line(-12,-9,-12,-2);c.line(12,-9,12,-2)
        elif k=='clock':c.circle(0,0,11,fill=0,stroke=1);c.line(0,0,0,7);c.line(0,0,6,-3)
        elif k=='pin':
            c.circle(0,4,8,fill=0,stroke=1);p=c.beginPath();p.moveTo(-6,-1);p.lineTo(0,-12);p.lineTo(6,-1);c.drawPath(p,stroke=1);c.circle(0,4,2.5,fill=0,stroke=1)
        elif k=='case':
            c.roundRect(-12,-8,24,16,2,fill=0,stroke=1);c.roundRect(-5,8,10,4,1,fill=0,stroke=1);c.line(-12,1,12,1);c.line(-3,2,-3,-2);c.line(3,2,3,-2);c.line(-3,-2,3,-2)
        elif k=='check':
            c.roundRect(-10,-11,20,22,2,fill=0,stroke=1)
            for y in (6,0,-6):c.line(-7,y,-5,y-2);c.line(-5,y-2,-2,y+2);c.line(1,y,7,y)
        elif k=='shield':
            p=c.beginPath();p.moveTo(0,12);p.lineTo(10,7);p.lineTo(8,-5);p.lineTo(0,-13);p.lineTo(-8,-5);p.lineTo(-10,7);p.close();c.drawPath(p,stroke=1);c.line(-4,0,-1,-3);c.line(-1,-3,5,4)
        else:
            c.line(0,-10,0,9);c.line(-12,11,0,9);c.line(0,9,12,11);c.line(-12,11,-12,-8);c.line(-12,-8,0,-10);c.line(0,-10,12,-8);c.line(12,-8,12,11)
        c.restoreState()

class CheckBox(Flowable):
    def __init__(self):super().__init__();self.width=15;self.height=17
    def draw(self):self.canv.setStrokeColor(BLUE);self.canv.setLineWidth(1);self.canv.roundRect(1,2,12,12,2,fill=0,stroke=1)

class Cover(Flowable):
    def __init__(self,title,subtitle):
        super().__init__();self.width=WIDTH;self.title=title;self.subtitle=subtitle
        self.style=ParagraphStyle('coverTitle',fontName='Helvetica-Bold',fontSize=23,leading=29,textColor=colors.white)
        self.para=Paragraph(escape(title),self.style);_,h=self.para.wrap(WIDTH-115,500)
        self.subtitle_para=Paragraph(escape(subtitle),ParagraphStyle('coverSubtitle',fontName='Helvetica',fontSize=10,leading=14,textColor=colors.HexColor('#D7E8FA')))
        _,sub_height=self.subtitle_para.wrap(WIDTH-115,500);self.height=max(155,h+sub_height+76)
    def draw(self):
        c=self.canv;c.setFillColor(NAVY);c.roundRect(0,0,self.width,self.height,12,fill=1,stroke=0)
        c.setFillColor(colors.HexColor('#A4DDFC'));c.setFont('Helvetica-Bold',9.5);c.drawString(18,self.height-24,'CONCURSO IA / GUIA DO EDITAL')
        _,h=self.para.wrap(WIDTH-115,500);self.para.drawOn(c,18,self.height-40-h)
        self.subtitle_para.wrap(WIDTH-115,500);self.subtitle_para.drawOn(c,18,16)
        x=self.width-62;y=self.height/2;c.setFillColor(colors.HexColor('#285581'));c.circle(x,y,42,fill=1,stroke=0);c.setStrokeColor(colors.white);c.setLineWidth(2)
        c.roundRect(x-20,y-26,40,52,4,fill=0,stroke=1)
        for off in (13,0,-13):c.line(x-12,y+off,x-9,y+off-3);c.line(x-9,y+off-3,x-5,y+off+3);c.line(x,y+off,x+12,y+off)

def render(data,target_data=None):
    validate(data)
    target=target_data.get('data') if isinstance(target_data,dict) else None
    styles=getSampleStyleSheet()
    styles['BodyText'].fontName='Helvetica';styles['BodyText'].fontSize=12;styles['BodyText'].leading=18;styles['BodyText'].textColor=INK;styles['BodyText'].spaceAfter=6
    styles.add(ParagraphStyle(name='GuideHead',fontName='Helvetica-Bold',fontSize=17,leading=23,textColor=NAVY,spaceAfter=0))
    styles.add(ParagraphStyle(name='GuideSmall',parent=styles['BodyText'],fontSize=10.5,leading=15,textColor=colors.HexColor('#34485F')))
    styles.add(ParagraphStyle(name='GuideValue',parent=styles['BodyText'],fontName='Helvetica-Bold',fontSize=14,leading=20))
    def p(text,style='BodyText'):return Paragraph(escape(str(text)).replace('\n','<br/>'),styles[style])
    def bold(text):return Paragraph('<b>'+escape(str(text))+'</b>',styles['BodyText'])
    def heading(title,kind):
        row=Table([[Icon(kind,46),p(title,'GuideHead')]],colWidths=[58,WIDTH-58]);row.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'MIDDLE'),('LEFTPADDING',(0,0),(-1,-1),0),('BOTTOMPADDING',(0,0),(-1,-1),7)]));row.keepWithNext=True
        return row
    def panel(title,text,kind):
        table=Table([[Icon(kind,38),[bold(title),p(text)]]],colWidths=[50,WIDTH-50],splitInRow=1)
        table.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,-1),colors.HexColor('#F0F5FC')),('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),10),('RIGHTPADDING',(0,0),(-1,-1),10),('TOPPADDING',(0,0),(-1,-1),10),('BOTTOMPADDING',(0,0),(-1,-1),8)]))
        return KeepTogether([table,Spacer(1,10)])
    story=[Cover(data['concurso']['titulo'],'Informações essenciais e conteúdo organizado para estudar'),Spacer(1,16),bold('Banca organizadora: '+data['concurso']['banca_organizadora']),p(data['concurso']['subtitulo']),p('Este guia não substitui o edital original nem suas retificações. Confira datas, requisitos e referências antes de tomar decisões.','GuideSmall'),Spacer(1,12)]
    metrics=[('calendar','Data e turno da prova',data['metricas_chave']['data_prova']+' / '+data['metricas_chave']['turno_prova']),('money','Remuneração máxima',data['metricas_chave']['remuneracao_maxima']),('people','Vagas',data['metricas_chave']['total_vagas']),('clock','Carga horária',data['metricas_chave']['carga_horaria'])]
    for kind,label,value in metrics:story.append(panel(label,value,kind))
    story.extend([Spacer(1,10),heading('1. Cronograma e datas importantes','calendar')])
    for item in data['cronograma']:story.append(panel(str(item['etapa'])+'. '+item['titulo']+(' — atenção à prova' if item['destaque'] else ''),item['periodo'],'calendar'))
    story.extend([Spacer(1,12),heading('2. Cargos, requisitos e remuneração','case')])
    story.append(p('Cargos em destaque na síntese executiva. Consulte a relação completa de cargos, vagas por localidade e requisitos específicos no edital original.','GuideSmall'))
    rows=[[bold('Cargo'),bold('Requisitos'),bold('Remuneração'),bold('Jornada')]]+[[bold(c['nome']),p(c['requisito']),bold(c['salario']),p(c['carga_horaria'])] for c in data['cargos']]
    if data['cargos']:
        table=Table(rows,colWidths=[125,172,115,WIDTH-412],repeatRows=1,splitInRow=1)
        table.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#DDEBFC')),('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,colors.HexColor('#F3F6FB')]),('VALIGN',(0,0),(-1,-1),'TOP'),('GRID',(0,0),(-1,-1),.35,colors.HexColor('#CAD8E8')),('TOPPADDING',(0,0),(-1,-1),10),('BOTTOMPADDING',(0,0),(-1,-1),10)]));story.extend([table,Spacer(1,14)])
    else:story.append(p('Cargos não informados no texto analisado.'))
    story.extend([heading('3. Cidades e orientações de acesso','pin'),panel('Cidades de aplicação da prova',data['locais_e_horarios']['cidades_prova'],'pin'),panel('Horários e portões',data['locais_e_horarios']['horarios_portoes'],'clock'),heading('4. Requisitos e documentos','shield')])
    for item in data['requisitos_e_documentos']:story.append(p('• '+item))
    if not data['requisitos_e_documentos']:story.append(p('Não informado no edital.'))
    story.extend([Spacer(1,10),panel('Orientação do edital para o dia da prova',data['dica_dia_prova'],'check'),PageBreak(),heading('5. Edital verticalizado: o que estudar','book'),p('Marque os quadrinhos conforme concluir os assuntos. A marcação é um apoio de estudo; não altera as regras da prova.','GuideSmall')])
    exams=target.get('exams',[]) if target else []
    if not exams:
        story.append(p('Conteúdo resumido disponível. Para listar os assuntos completos e separados por prova, importe o edital novamente com a análise estruturada ativa.','GuideSmall'))
        exams=[{'label':'Conteúdo da síntese executiva','total_questions':data['distribuicao_pontos']['total_questoes'],'duration_minutes':None,'scoring':'Regras detalhadas: consulte o documento original.','warnings':[],'subjects':[{'name':s['disciplina'],'questions':s['questoes'],'weight':s['peso'],'topics':s['topicos'],'evidence':''} for s in data['materias_e_pesos']]}]
    for number,exam in enumerate(exams,1):
        if number>1:story.append(PageBreak())
        story.extend([Spacer(1,10),heading('Prova '+str(number)+' — '+exam['label'],'case'),bold('Questões: '+str(exam['total_questions'] if exam['total_questions'] is not None else 'Não informado')+' | Duração: '+str(exam['duration_minutes'] if exam['duration_minutes'] is not None else 'Não informado')+' min'),p(exam['scoring'])])
        for subject in exam['subjects']:
            meta=('Questões: '+str(subject['questions']) if subject['questions'] is not None else 'Quantidade de questões não informada')+' | '+('Peso: '+str(subject['weight']) if subject['weight'] is not None else 'Peso não informado')
            story.extend([CondPageBreak(170),Spacer(1,10),heading(subject['name'],'book'),bold(meta)])
            rows=[[bold('Feito'),bold('Assunto / conteúdo exigido')]]+[[CheckBox(),p(str(i)+'. '+topic)] for i,topic in enumerate(subject['topics'],1)]
            table=Table(rows,colWidths=[51,WIDTH-51],repeatRows=1,splitInRow=1)
            table.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#EDE4FA')),('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,colors.HexColor('#F8F5FC')]),('VALIGN',(0,0),(-1,-1),'TOP'),('GRID',(0,0),(-1,-1),.35,colors.HexColor('#DDD2ED')),('TOPPADDING',(0,0),(-1,-1),9),('BOTTOMPADDING',(0,0),(-1,-1),9)]));story.extend([table,Spacer(1,7)])
            if subject.get('evidence'):story.append(p('Referência no edital: '+subject['evidence'],'GuideSmall'))
        essay=exam.get('essay')
        if essay:
            story.extend([Spacer(1,10),heading('Redação / prova discursiva','check'),bold('Tipo de texto: '+essay['genre']),p('Linhas: '+str(essay['min_lines'] if essay['min_lines'] is not None else 'mínimo não informado')+' a '+str(essay['max_lines'] if essay['max_lines'] is not None else 'máximo não informado'))])
            for criterion in essay['criteria']:story.extend([bold(criterion['name']+' — '+str(criterion['max_score'] if criterion['max_score'] is not None else 'pontuação não informada')),p(criterion['description'])])
        for note in exam.get('warnings',[]):story.append(p('Atenção: '+note,'GuideSmall'))
    if target:
        for note in target.get('warnings',[]):story.append(p('Atenção: '+note,'GuideSmall'))
    story.extend([Spacer(1,15),panel('Confira o documento original','Informações ausentes não foram presumidas. A síntese executiva destaca até seis cargos; o conteúdo verticalizado utiliza os assuntos retornados pela análise estruturada. A IA pode omitir ou interpretar informações incorretamente: confira os anexos e as referências.','shield')])
    def footer(c,doc):
        c.saveState();c.setStrokeColor(colors.HexColor('#CAD8E8'));c.line(44,37,A4[0]-44,37);c.setFont('Helvetica',9);c.setFillColor(INK);c.drawString(44,23,'Concurso IA | Guia de apoio ao edital');c.drawRightString(A4[0]-44,23,'Página '+str(doc.page))
        if doc.page>1:c.setFillColor(BLUE);c.rect(44,A4[1]-34,28,3,stroke=0,fill=1);c.setFont('Helvetica-Bold',9);c.drawString(80,A4[1]-35,'GUIA DO EDITAL / CONTEÚDO VERTICALIZADO')
        c.restoreState()
    buf=BytesIO();SimpleDocTemplate(buf,pagesize=A4,leftMargin=44,rightMargin=44,topMargin=49,bottomMargin=51,title='Guia do edital — '+data['concurso']['titulo'],author='Concurso IA').build(story,onFirstPage=footer,onLaterPages=footer)
    return buf.getvalue()

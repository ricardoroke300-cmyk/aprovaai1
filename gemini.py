"""Gemini REST adapter. Never exposes provider error bodies or credentials."""
import json, os, re, urllib.request, urllib.error
import cancellation

def parts(content):
    if isinstance(content,str):return [{'text':content}]
    result=[]
    for message in content:
        for item in message['content']:
            if item['type']=='input_text':result.append({'text':item['text']})
            elif item['type']=='input_image':
                header,data=item['image_url'].split(',',1)
                result.append({'inlineData':{'mimeType':header[5:].split(';')[0],'data':data}})
            else:raise ValueError('Tipo de entrada não suportado')
    return result

def generate(instructions,content,schema,search=False):
    cancellation.check()
    key=os.getenv('GEMINI_API_KEY','');model=os.getenv('GEMINI_MODEL','')
    if not key or not model:raise RuntimeError('Configure GEMINI_API_KEY e GEMINI_MODEL no arquivo .env.')
    if not re.fullmatch(r'[a-zA-Z0-9._-]+',model):raise RuntimeError('Nome do modelo Gemini inválido.')
    payload={'systemInstruction':{'parts':[{'text':instructions}]},'contents':[{'role':'user','parts':parts(content)}],
             'generationConfig':{'responseMimeType':'application/json','responseJsonSchema':schema,'maxOutputTokens':16000}}
    if search:
        payload['tools']=[{'google_search':{}}]
        payload['generationConfig']={'maxOutputTokens':4000}
    request=urllib.request.Request('https://generativelanguage.googleapis.com/v1beta/models/'+model+':generateContent',
        data=json.dumps(payload).encode(),headers={'x-goog-api-key':key,'Content-Type':'application/json'})
    try:
        with urllib.request.urlopen(request,timeout=240) as response:result=json.load(response)
    except urllib.error.HTTPError as error:
        hints={400:'Confira o modelo, o tamanho da entrada e o contrato JSON.',403:'Confira a chave e as permissões.',404:'Confira GEMINI_MODEL; o modelo pode não estar disponível na conta.',429:'Cota atingida. Confira os limites e o faturamento.'}
        raise RuntimeError(f'Gemini não concluiu a operação (HTTP {error.code}). '+hints.get(error.code,'Tente novamente mais tarde.')) from None
    except (urllib.error.URLError,TimeoutError):raise RuntimeError('Não foi possível conectar ao Gemini.') from None
    cancellation.check()
    candidates=result.get('candidates',[])
    if not candidates:raise RuntimeError('O Gemini não retornou conteúdo. Tente novamente. Nenhum resultado parcial foi usado.')
    reason=candidates[0].get('finishReason')
    if reason=='MAX_TOKENS':raise RuntimeError('A resposta atingiu o limite de saída do modelo. Escolha um assunto mais específico ou reduza a quantidade solicitada. Nenhum resultado parcial foi usado.')
    if reason!='STOP':raise RuntimeError('O Gemini não concluiu a resposta. Nenhum resultado parcial foi usado.')
    text=''.join(p.get('text','') for p in candidates[0].get('content',{}).get('parts',[]) if not p.get('thought'))
    if search:
        metadata=candidates[0].get('groundingMetadata',{})
        sources=[{'title':chunk['web'].get('title','Fonte'),'url':chunk['web'].get('uri','')} for chunk in metadata.get('groundingChunks',[]) if chunk.get('web',{}).get('uri','').startswith('https://')]
        return {'text':text,'sources':sources}
    try:return json.loads(text)
    except (ValueError,TypeError):raise RuntimeError('O Gemini retornou JSON inválido. Tente novamente.') from None

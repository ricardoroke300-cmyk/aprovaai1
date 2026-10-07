"""Session-private component RPC adapter for the existing authenticated API."""
import base64, io, json, os, re
from urllib.parse import urlsplit
import cloud_server

def dispatch(request,session,ip='streamlit'):
    identifier=request.get('id','')
    if not isinstance(identifier,str) or not re.fullmatch(r'[a-f0-9]{32}',identifier):raise ValueError('Identificador inválido.')
    path=request.get('path','');method=request.get('method','GET')
    if not isinstance(path,str) or not path.startswith('/api/') or len(path)>500 or method not in ('GET','POST','PUT'):raise ValueError('Solicitação inválida.')
    parsed=urlsplit(path)
    if parsed.netloc or parsed.scheme or parsed.fragment:raise ValueError('Endereço inválido.')
    raw=request.get('body','')
    if not isinstance(raw,str) or len(raw.encode())>32*1024*1024:raise ValueError('Solicitação maior que o limite.')
    headers=request.get('headers',{})
    if not isinstance(headers,dict):raise ValueError('Cabeçalhos inválidos.')
    origin=os.environ['APROVA_PUBLIC_URL'];host=urlsplit(origin).netloc
    env={'PATH_INFO':parsed.path,'QUERY_STRING':parsed.query,'REQUEST_METHOD':method,'HTTP_HOST':host,'HTTP_ORIGIN':origin,'HTTP_X_GUIDE_TOKEN':os.environ['APROVA_WEB_TOKEN'],'HTTP_COOKIE':session.get('cookie',''),'HTTP_X_ACCOUNT_ID':str(headers.get('X-Account-Id',''))[:100],'HTTP_X_GENERATION_ID':str(headers.get('X-Generation-Id',''))[:100],'REMOTE_ADDR':ip,'CONTENT_LENGTH':str(len(raw.encode())),'wsgi.input':io.BytesIO(raw.encode())}
    result={}
    def start(status,response_headers):
        result.update(status=int(status.split()[0]),headers=dict(response_headers))
        cookie=result['headers'].get('Set-Cookie')
        if cookie:session['cookie']=cookie
    binary=b''.join(cloud_server.application(env,start))
    return {'id':identifier,'status':result['status'],'mime':result['headers']['Content-Type'],'body':base64.b64encode(binary).decode()}

def batch(value,session,ip='streamlit'):
    if not isinstance(value,dict):return None
    event=value.get('event','')
    if not isinstance(event,str) or not re.fullmatch(r'[a-f0-9]{32}',event):raise ValueError('Evento inválido.')
    if session.get('last_event')==event:return None
    requests=value.get('requests',[])
    if not isinstance(requests,list) or len(requests)>20 or not all(isinstance(r,dict) for r in requests):raise ValueError('Lote inválido.')
    replies=session.setdefault('replies',{});ids={r.get('id') for r in requests}
    # Keep only replies still awaiting delivery; a rerun never repeats a request.
    for identifier in list(replies):
        if identifier not in ids:del replies[identifier]
    for request in requests:
        identifier=request.get('id')
        if identifier not in replies:replies[identifier]=dispatch(request,session,ip)
    session['last_event']=event
    return list(replies.values())

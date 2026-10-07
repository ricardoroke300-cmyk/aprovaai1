"""WSGI API for a central aprova.ai installation. Serve with Gunicorn."""
import hashlib, json, logging, os, re, secrets
from pathlib import Path
from urllib.parse import urlsplit, parse_qs
import auth, cloud_store
ROOT=Path(__file__).parent
GENERATION_PATHS={'/api/tutor/answer','/api/practice/next','/api/exams/generate','/api/essay/theme','/api/essay/transcribe','/api/essay/grade','/api/material/pdf','/api/board/analyze','/api/target/analyze','/api/guide'}

def config():
    origin=os.getenv('APROVA_PUBLIC_URL','').rstrip('/')
    parsed=urlsplit(origin)
    if parsed.scheme not in ('http','https') or not parsed.hostname or parsed.path or parsed.query or parsed.fragment or parsed.username:raise RuntimeError('Configure APROVA_PUBLIC_URL com a URL pública do aplicativo.')
    if parsed.scheme!='https' and parsed.hostname not in ('localhost','127.0.0.1'):raise RuntimeError('A URL pública precisa usar HTTPS.')
    token=os.getenv('APROVA_WEB_TOKEN','')
    if len(token)<32 or 'CHANGE_ME' in token:raise RuntimeError('Configure APROVA_WEB_TOKEN com um valor aleatório de pelo menos 32 caracteres.')
    if not os.getenv('APROVA_DATABASE_URL') or not os.getenv('APROVA_DATA_DIR'):raise RuntimeError('Configure o banco central e APROVA_DATA_DIR.')
    return origin,parsed,token

def respond(start,status,data,mime='application/json',cookie=None):
    if not isinstance(data,bytes):data=json.dumps(data,ensure_ascii=False).encode()
    labels={200:'OK',202:'Accepted',400:'Bad Request',401:'Unauthorized',403:'Forbidden',404:'Not Found',409:'Conflict',413:'Payload Too Large',422:'Unprocessable Entity',429:'Too Many Requests',500:'Internal Server Error',503:'Service Unavailable'}
    headers=[('Content-Type',mime),('Content-Length',str(len(data))),('Cache-Control','no-store'),('X-Content-Type-Options','nosniff'),('X-Frame-Options','DENY'),('Referrer-Policy','same-origin')]
    if cookie:headers.append(('Set-Cookie',cookie))
    start(str(status)+' '+labels.get(status,'Error'),headers)
    return [data]

def body(environ,maximum=24*1024*1024):
    try:size=int(environ.get('CONTENT_LENGTH','0'))
    except ValueError:raise ValueError('Tamanho de solicitação inválido.') from None
    if not 0<size<=maximum:raise ValueError('Solicitação vazia ou maior que o limite permitido.')
    raw=environ['wsgi.input'].read(size)
    if len(raw)!=size:raise ValueError('Solicitação incompleta.')
    data=json.loads(raw)
    if not isinstance(data,dict):raise ValueError('Envie um objeto JSON válido.')
    return data

def application(environ,start_response):
    context=None
    try:
        origin,parsed,token=config()
        path=environ.get('PATH_INFO','/');method=environ.get('REQUEST_METHOD','GET')
        host=environ.get('HTTP_HOST','').lower()
        if host!=parsed.netloc.lower():return respond(start_response,403,{'error':'Endereço não autorizado.'})
        if method=='GET' and path=='/healthz':
            from cloud_db import connect
            with connect() as db:db.execute('SELECT 1')
            return respond(start_response,200,{'ok':True})
        if method=='GET' and path in ('/','/index.html','/app.html'):
            html=(ROOT/'app.html').read_text().replace("const SERVICE_TOKEN='__LOCAL_TOKEN__';",'const SERVICE_TOKEN='+json.dumps(token)+';',1).replace('const CLOUD_MODE=false;','const CLOUD_MODE=true;',1)
            return respond(start_response,200,html.encode(),'text/html; charset=utf-8')
        if not path.startswith('/api/'):return respond(start_response,404,{'error':'Não encontrado.'})
        if not secrets.compare_digest(environ.get('HTTP_X_GUIDE_TOKEN',''),token):return respond(start_response,403,{'error':'Acesso não autorizado.'})
        if method not in ('GET','POST','PUT'):return respond(start_response,400,{'error':'Método não permitido.'})
        if method!='GET' and environ.get('HTTP_ORIGIN','')!=origin:return respond(start_response,403,{'error':'Origem não autorizada.'})
        cookie=environ.get('HTTP_COOKIE','')
        user=auth.identify(cookie)
        if method=='GET' and path=='/api/auth/me':return respond(start_response,200,{'user':user,'cloud':True})
        if method=='POST' and path in ('/api/auth/login','/api/auth/register'):
            payload=body(environ,4096)
            cloud_store.throttle('email:'+str(payload.get('email','')).strip().casefold())
            ip=environ.get('HTTP_X_FORWARDED_FOR',environ.get('REMOTE_ADDR','')).split(',')[0].strip()
            cloud_store.throttle('auth-ip:'+ip,60)
            data,new_cookie=(auth.register if path.endswith('/register') else auth.login)(payload)
            if parsed.scheme=='https':new_cookie+='; Secure'
            return respond(start_response,200,data,cookie=new_cookie)
        if not user:return respond(start_response,401,{'error':'Entre com uma conta e licença ativa para continuar.'})
        if environ.get('HTTP_X_ACCOUNT_ID','')!=user['id']:return respond(start_response,401,{'error':'A conta mudou em outra aba. Atualize a página.'})
        context=auth.CURRENT.set(user)
        if method=='POST' and path=='/api/auth/logout':
            new_cookie=auth.logout(cookie)+('; Secure' if parsed.scheme=='https' else '')
            return respond(start_response,200,{'ok':True},cookie=new_cookie)
        if path=='/api/progress':
            if method=='GET':return respond(start_response,200,cloud_store.progress(user['id']))
            if method=='PUT':
                payload=body(environ,32*1024*1024)
                return respond(start_response,200,cloud_store.save_progress(user['id'],payload.get('version'),payload.get('data')))
        if method=='GET' and path=='/api/target':
            import target
            return respond(start_response,200,{'target':target.read()})
        if method=='GET' and path=='/api/learning':
            import learning
            return respond(start_response,200,{'ready':learning.ready(),'config':{'enabled':False},'count':0,'status':'Gerações sob demanda com fila.'})
        if method=='GET' and path=='/api/generation/status':
            client_id=parse_qs(environ.get('QUERY_STRING','')).get('id',[''])[0][:100]
            task=cloud_store.status(user['id'],client_id=client_id)
            return respond(start_response,200,{'stage':task['stage'] if task else 'Preparando geração…'})
        if method=='POST' and path=='/api/generation/cancel':
            client_id=environ.get('HTTP_X_GENERATION_ID','')
            if not re.fullmatch(r'[A-Za-z0-9._-]{1,100}',client_id):raise ValueError('Identificador de geração inválido.')
            return respond(start_response,200,cloud_store.cancel(user['id'],client_id))
        match=re.fullmatch(r'/api/jobs/([a-f0-9]{32})(/result)?',path)
        if method=='GET' and match:
            task=cloud_store.status(user['id'],identifier=match[1])
            if not task:return respond(start_response,404,{'error':'Geração não encontrada.'})
            if match[2]:
                result=cloud_store.result(user['id'],match[1])
                if not result:return respond(start_response,409,{'error':'O resultado ainda não está disponível.'})
                return respond(start_response,200,bytes(result['result']),result['mime'])
            return respond(start_response,200,task)
        if method=='POST' and path=='/api/ai/settings':return respond(start_response,200,{'enabled':False,'status':'Geração sob demanda.'})
        if method=='POST' and path in GENERATION_PATHS:
            client_id=environ.get('HTTP_X_GENERATION_ID','')
            if not re.fullmatch(r'[A-Za-z0-9._-]{1,100}',client_id):raise ValueError('Identificador de geração inválido.')
            payload=body(environ)
            job=cloud_store.submit(user['id'],client_id,path,payload)
            return respond(start_response,202,{'job_id':job})
        return respond(start_response,404,{'error':'Não encontrado.'})
    except cloud_store.Conflict as error:return respond(start_response,409,{'error':str(error)})
    except cloud_store.Busy as error:return respond(start_response,429,{'error':str(error)})
    except (ValueError,RuntimeError) as error:return respond(start_response,422,{'error':str(error)})
    except Exception as error:
        logging.error('Central API failure: %s',type(error).__name__)
        return respond(start_response,503,{'error':'O serviço central está temporariamente indisponível. Tente novamente.'})
    finally:
        if context is not None:auth.CURRENT.reset(context)

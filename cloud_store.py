"""Durable student progress and a leased PostgreSQL generation queue."""
import datetime, hashlib, json, os, secrets, sqlite3, time, uuid
from cloud_db import connect

class Conflict(ValueError):pass
class Busy(ValueError):pass
LEASE_SECONDS=45

def record_call(user_id):
    day=datetime.datetime.now(datetime.timezone.utc).date().isoformat()
    with connect() as db:db.execute('INSERT INTO ai_calls VALUES (?,?,1) ON CONFLICT(day,user_id) DO UPDATE SET calls=ai_calls.calls+1',(day,user_id))

def throttle(key,limit=20):
    bucket=int(time.time()/60)
    with connect() as db:
        row=db.execute('INSERT INTO rate_limits VALUES (?,?,1) ON CONFLICT(key) DO UPDATE SET hits=CASE WHEN rate_limits.bucket=excluded.bucket THEN rate_limits.hits+1 ELSE 1 END,bucket=excluded.bucket RETURNING hits',(hashlib.sha256(key.encode()).hexdigest(),bucket)).fetchone()
        if row['hits']>limit:raise Busy('Muitas tentativas. Aguarde um minuto antes de tentar novamente.')

def user_for_worker(user_id):
    import auth
    with auth.connect() as db:
        row=db.execute('SELECT * FROM users WHERE id=?',(user_id,)).fetchone()
        return auth.public(row) if row and auth.licensed(db,row) else None

def progress(user_id):
    with connect() as db:row=db.execute('SELECT version,data FROM progress WHERE user_id=?',(user_id,)).fetchone()
    return {'version':row['version'],'data':json.loads(row['data'])} if row else {'version':0,'data':None}

def save_progress(user_id,version,data):
    if type(version) is not int or version<0 or not isinstance(data,dict) or data.get('version')!=1 or not isinstance(data.get('attempts'),list) or not isinstance(data.get('completed'),list):raise ValueError('Progresso inválido.')
    encoded=json.dumps(data,ensure_ascii=False)
    if len(encoded.encode())>32*1024*1024:raise ValueError('Seu progresso excede o tamanho permitido para sincronização.')
    try:
        with connect() as db:
            if not db.postgres:db.execute('BEGIN IMMEDIATE')
            row=db.execute('SELECT version FROM progress WHERE user_id=?'+(' FOR UPDATE' if db.postgres else ''),(user_id,)).fetchone()
            if (row['version'] if row else 0)!=version:raise Conflict('Outra sessão atualizou seu progresso. Exporte sua cópia local e recarregue para sincronizar.')
            if row:db.execute('UPDATE progress SET version=?,data=?,updated=? WHERE user_id=?',(version+1,encoded,time.time(),user_id))
            else:db.execute('INSERT INTO progress VALUES (?,?,?,?)',(user_id,1,encoded,time.time()))
        return {'version':version+1}
    except sqlite3.IntegrityError:raise Conflict('Outra sessão atualizou seu progresso. Recarregue para sincronizar.') from None

def maintenance(db):
    now=time.time()
    db.execute('DELETE FROM sessions WHERE expires<=?',(now,))
    db.execute("UPDATE jobs SET status='failed',stage='Processamento interrompido',error='O processamento foi interrompido. Tente gerar novamente.',payload='',updated=? WHERE status='running' AND lease_until<?",(now,now))
    db.execute("UPDATE jobs SET status='failed',stage='Fila expirada',error='A tarefa ficou tempo demais na fila. Tente gerar novamente.',payload='',updated=? WHERE status='pending' AND created<?",(now,now-3600))
    db.execute("DELETE FROM jobs WHERE status NOT IN ('pending','running') AND updated<?",(now-7*86400,))
    db.execute('DELETE FROM rate_limits WHERE bucket<?',(int(now/60)-60,))
    db.execute('DELETE FROM ai_calls WHERE day<?',((datetime.datetime.now(datetime.timezone.utc)-datetime.timedelta(days=90)).date().isoformat(),))

def submit(user_id,client_id,path,payload):
    encoded=json.dumps(payload,ensure_ascii=False,sort_keys=True)
    try:
        with connect() as db:
            db.execute('BEGIN IMMEDIATE');maintenance(db)
            existing=db.execute('SELECT id,path,payload,status FROM jobs WHERE user_id=? AND client_id=?',(user_id,client_id)).fetchone()
            if existing:
                if existing['path']!=path or (existing['payload'] and existing['payload']!=encoded):raise Conflict('Identificador de geração já utilizado.')
                return existing['id']
            if db.execute("SELECT 1 FROM jobs WHERE user_id=? AND status IN ('pending','running')",(user_id,)).fetchone():raise Busy('Você já tem uma geração em andamento. Aguarde ou cancele essa geração.')
            count=db.execute("SELECT COUNT(*) AS n FROM jobs WHERE status IN ('pending','running')").fetchone()['n']
            if count>=int(os.getenv('APROVA_MAX_QUEUE','1000')):raise Busy('A fila está cheia. Tente novamente em alguns minutos.')
            identifier=uuid.uuid4().hex;now=time.time()
            db.execute('INSERT INTO jobs (id,user_id,client_id,path,payload,status,stage,created,updated) VALUES (?,?,?,?,?,?,?,?,?)',(identifier,user_id,client_id,path,encoded,'pending','Na fila — aguardando processamento…',now,now))
            return identifier
    except sqlite3.IntegrityError:raise Busy('Você já tem uma geração em andamento. Aguarde ou cancele essa geração.') from None

def claim():
    with connect() as db:
        if not db.postgres:db.execute('BEGIN IMMEDIATE')
        maintenance(db)
        row=db.execute("SELECT id,user_id,path,payload FROM jobs WHERE status='pending' ORDER BY created,id LIMIT 1"+(' FOR UPDATE SKIP LOCKED' if db.postgres else '')).fetchone()
        if not row:return None
        lease=secrets.token_hex(16);now=time.time()
        db.execute("UPDATE jobs SET status='running',stage='Preparando conteúdo…',lease=?,lease_until=?,updated=? WHERE id=?",(lease,now+LEASE_SECONDS,now,row['id']))
        return {**row,'lease':lease,'payload':json.loads(row['payload'])}

def heartbeat(identifier,lease,stage):
    with connect() as db:
        row=db.execute("SELECT cancelled FROM jobs WHERE id=? AND lease=? AND status='running' AND lease_until>?",(identifier,lease,time.time())).fetchone()
        if not row:return False
        db.execute('UPDATE jobs SET stage=?,lease_until=?,updated=? WHERE id=? AND lease=?',(stage,time.time()+LEASE_SECONDS,time.time(),identifier,lease))
        return not bool(row['cancelled'])

def finish(identifier,lease,result=None,mime='application/json',error=None):
    with connect() as db:
        row=db.execute("SELECT cancelled FROM jobs WHERE id=? AND lease=? AND status='running' AND lease_until>?",(identifier,lease,time.time())).fetchone()
        if not row:return False
        status='cancelled' if row['cancelled'] else 'failed' if error else 'done'
        db.execute('UPDATE jobs SET status=?,stage=?,result=?,mime=?,error=?,payload=?,updated=? WHERE id=? AND lease=?',(status,'Geração cancelada.' if status=='cancelled' else 'Não foi possível concluir.' if error else 'Conteúdo pronto.',result if status=='done' else None,mime,error,'',time.time(),identifier,lease))
        return True

def cancel(user_id,client_id):
    with connect() as db:
        db.execute("UPDATE jobs SET cancelled=1,stage='Cancelando geração…',updated=? WHERE user_id=? AND client_id=? AND status='running'",(time.time(),user_id,client_id))
        db.execute("UPDATE jobs SET status='cancelled',cancelled=1,stage='Geração cancelada.',payload='',updated=? WHERE user_id=? AND client_id=? AND status='pending'",(time.time(),user_id,client_id))
    return {'cancelled':True}

def status(user_id,identifier=None,client_id=None):
    with connect() as db:
        maintenance(db)
        row=db.execute('SELECT id,status,stage,error,created FROM jobs WHERE user_id=? AND '+('id=?' if identifier else 'client_id=?'),(user_id,identifier or client_id)).fetchone()
        if not row:return None
        result=dict(row)
        if row['status']=='pending':result['position']=db.execute("SELECT COUNT(*) AS n FROM jobs WHERE status='pending' AND created<=?",(row['created'],)).fetchone()['n']
        return result

def result(user_id,identifier):
    with connect() as db:return db.execute("SELECT result,mime FROM jobs WHERE user_id=? AND id=? AND status='done'",(user_id,identifier)).fetchone()

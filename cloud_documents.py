"""Durable per-account JSON documents; no local disk dependency in cloud mode."""
import json, os, time
import auth
from cloud_db import connect

def enabled():return bool(os.getenv('APROVA_DATABASE_URL'))
def owner():
    user=auth.CURRENT.get()
    if not user:raise RuntimeError('Conta necessária para acessar os documentos.')
    return user['id']
def read(name,default=None):
    with connect() as db:row=db.execute('SELECT data FROM documents WHERE user_id=? AND name=?',(owner(),name)).fetchone()
    return json.loads(row['data']) if row else default
def write(name,data):
    encoded=json.dumps(data,ensure_ascii=False)
    if len(encoded.encode())>32*1024*1024:raise ValueError('Documento maior que o limite de armazenamento.')
    with connect() as db:db.execute('INSERT INTO documents VALUES (?,?,?,?) ON CONFLICT(user_id,name) DO UPDATE SET data=excluded.data,updated=excluded.updated',(owner(),name,encoded,time.time()))
def materials(requested=None):
    with connect() as db:
        sql='SELECT data FROM documents WHERE user_id=? AND name LIKE ?'
        params=[owner(),'material/%']
        if requested:
            subject="data::jsonb->'context'->>'subject'" if db.postgres else "json_extract(data,'$.context.subject')"
            topic="data::jsonb->'context'->>'topic'" if db.postgres else "json_extract(data,'$.context.topic')"
            sql+=' AND ('+' OR '.join('('+subject+'=? AND '+topic+'=?)' for _ in requested)+')'
            for name,detail in requested:params.extend((name,detail))
        rows=db.execute(sql+' ORDER BY updated DESC LIMIT 1000',tuple(params)).fetchall()
    return [json.loads(row['data']) for row in rows]

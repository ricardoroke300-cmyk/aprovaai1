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
def materials():
    with connect() as db:rows=db.execute('SELECT data FROM documents WHERE user_id=? AND name LIKE ? ORDER BY updated DESC LIMIT 1000',(owner(),'material/%')).fetchall()
    return [json.loads(row['data']) for row in rows]

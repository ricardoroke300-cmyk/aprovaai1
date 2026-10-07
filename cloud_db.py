"""Shared database: PostgreSQL in production, explicit SQLite mode for tests."""
import os, sqlite3, threading
from contextlib import contextmanager
from pathlib import Path
_BOOTSTRAPPED=set()
_BOOT_LOCK=threading.Lock()

SCHEMA=[
"CREATE TABLE IF NOT EXISTS documents (user_id TEXT NOT NULL,name TEXT NOT NULL,data TEXT NOT NULL,updated DOUBLE PRECISION NOT NULL,PRIMARY KEY(user_id,name))",
"CREATE TABLE IF NOT EXISTS users (id TEXT PRIMARY KEY,email TEXT UNIQUE NOT NULL,name TEXT NOT NULL,salt TEXT NOT NULL,password TEXT NOT NULL,legacy_owner INTEGER NOT NULL,license_hash TEXT)",
"CREATE TABLE IF NOT EXISTS sessions (token TEXT PRIMARY KEY,user_id TEXT NOT NULL,expires DOUBLE PRECISION NOT NULL)",
"CREATE TABLE IF NOT EXISTS licenses (key_hash TEXT PRIMARY KEY,id TEXT UNIQUE NOT NULL,email TEXT NOT NULL,expires DOUBLE PRECISION,active INTEGER NOT NULL,user_id TEXT)",
"CREATE TABLE IF NOT EXISTS progress (user_id TEXT PRIMARY KEY,version INTEGER NOT NULL,data TEXT NOT NULL,updated DOUBLE PRECISION NOT NULL)",
"CREATE TABLE IF NOT EXISTS jobs (id TEXT PRIMARY KEY,user_id TEXT NOT NULL,client_id TEXT NOT NULL,path TEXT NOT NULL,payload TEXT NOT NULL,status TEXT NOT NULL,stage TEXT NOT NULL,created DOUBLE PRECISION NOT NULL,updated DOUBLE PRECISION NOT NULL,cancelled INTEGER NOT NULL DEFAULT 0,lease TEXT,lease_until DOUBLE PRECISION,result BYTEA,mime TEXT,error TEXT,UNIQUE(user_id,client_id))",
"CREATE INDEX IF NOT EXISTS jobs_pending ON jobs(status,created)",
"CREATE UNIQUE INDEX IF NOT EXISTS one_active_job_per_student ON jobs(user_id) WHERE status IN ('pending','running')",
"CREATE TABLE IF NOT EXISTS ai_calls (day TEXT NOT NULL,user_id TEXT NOT NULL,calls INTEGER NOT NULL,PRIMARY KEY(day,user_id))",
"CREATE TABLE IF NOT EXISTS rate_limits (key TEXT PRIMARY KEY,bucket INTEGER NOT NULL,hits INTEGER NOT NULL)"
]

class Row(dict):
    def __getitem__(self,key):
        return list(self.values())[key] if isinstance(key,int) else super().__getitem__(key)

class Cursor:
    def __init__(self,cursor):self.cursor=cursor
    @property
    def rowcount(self):return self.cursor.rowcount
    def row(self,row):return Row(row) if row is not None else None
    def fetchone(self):return self.row(self.cursor.fetchone())
    def fetchall(self):return [self.row(row) for row in self.cursor.fetchall()]
    def __iter__(self):return iter(self.fetchall())

class Connection:
    def __init__(self,raw,postgres):self.raw=raw;self.postgres=postgres
    def execute(self,sql,params=()):
        if sql=='BEGIN IMMEDIATE' and self.postgres:
            self.raw.execute('BEGIN')
            return Cursor(self.raw.execute('SELECT pg_advisory_xact_lock(773511)'))
        if self.postgres:sql=sql.replace('?','%s')
        try:return Cursor(self.raw.execute(sql,params))
        except Exception as error:
            if self.postgres and getattr(error,'sqlstate',None)=='23505':raise sqlite3.IntegrityError('Registro duplicado') from None
            raise
    def commit(self):self.raw.commit()
    def rollback(self):self.raw.rollback()
    def close(self):self.raw.close()

def configured():return bool(os.getenv('APROVA_DATABASE_URL'))
def raw_connect():
    dsn=os.getenv('APROVA_DATABASE_URL','')
    if dsn.startswith('sqlite:///') and os.getenv('APROVA_TEST_MODE')=='1':
        path=Path(dsn[len('sqlite:///'):]);path.parent.mkdir(parents=True,exist_ok=True)
        raw=sqlite3.connect(path,timeout=15);raw.row_factory=sqlite3.Row
        raw.execute('PRAGMA journal_mode=WAL');raw.execute('PRAGMA busy_timeout=15000')
        return Connection(raw,False)
    if not dsn.startswith(('postgresql://','postgres://')):raise RuntimeError('Configure APROVA_DATABASE_URL com PostgreSQL para o servidor central.')
    try:
        import psycopg
        from psycopg.rows import dict_row
    except ImportError:raise RuntimeError('Instale as dependências de requirements-cloud.txt.') from None
    from urllib.parse import urlsplit
    parsed=urlsplit(dsn)
    if parsed.port==6543:raise RuntimeError('Use a conexão direta ou o Session pooler (porta 5432) do Supabase para este servidor persistente.')
    options={'row_factory':dict_row,'connect_timeout':10,'prepare_threshold':None}
    if parsed.hostname not in ('db','postgres','localhost','127.0.0.1'):options['sslmode']='require'
    raw=psycopg.connect(dsn,**options)
    raw.execute('SET search_path TO aprova_private, pg_catalog');raw.commit()
    return Connection(raw,True)

@contextmanager
def connect():
    db=raw_connect()
    try:
        dsn=os.getenv('APROVA_DATABASE_URL')
        with _BOOT_LOCK:
            if dsn not in _BOOTSTRAPPED:
                if db.postgres:
                    db.execute('SELECT pg_advisory_xact_lock(773510)')
                    db.execute('CREATE SCHEMA IF NOT EXISTS aprova_private')
                    db.execute('REVOKE ALL ON SCHEMA aprova_private FROM PUBLIC')
                for sql in SCHEMA:db.execute(sql)
                if db.postgres:
                    db.execute('ALTER TABLE users ADD COLUMN IF NOT EXISTS license_hash TEXT')
                    db.execute('REVOKE ALL ON ALL TABLES IN SCHEMA aprova_private FROM PUBLIC')
                    for table in ('users','sessions','licenses','progress','jobs','ai_calls','rate_limits','documents'):
                        db.execute('ALTER TABLE '+table+' ENABLE ROW LEVEL SECURITY')
                    for role in ('anon','authenticated'):
                        if db.execute('SELECT 1 FROM pg_roles WHERE rolname=?',(role,)).fetchone():
                            db.execute('REVOKE ALL ON SCHEMA aprova_private FROM '+role)
                            db.execute('REVOKE ALL ON ALL TABLES IN SCHEMA aprova_private FROM '+role)
                db.commit();_BOOTSTRAPPED.add(dsn)
        yield db
        db.commit()
    except BaseException:
        db.rollback();raise
    finally:db.close()

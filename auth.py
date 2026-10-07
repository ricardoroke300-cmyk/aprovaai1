"""Local accounts, hashed passwords and revocable browser sessions."""
import hashlib, hmac, re, secrets, sqlite3, time, shutil, os
from pathlib import Path
from http.cookies import SimpleCookie
from contextvars import ContextVar
from contextlib import contextmanager

DB=Path(__file__).parent/'accounts.sqlite3'
CURRENT=ContextVar('account',default=None)
COOKIE='aprova_session'
TTL=7*24*60*60

@contextmanager
def connect():
    if os.getenv('APROVA_DATABASE_URL'):
        from cloud_db import connect as central_connect
        with central_connect() as db:yield db
        return
    db=sqlite3.connect(DB,timeout=10)
    db.row_factory=sqlite3.Row
    db.execute('CREATE TABLE IF NOT EXISTS users (id TEXT PRIMARY KEY,email TEXT UNIQUE NOT NULL,name TEXT NOT NULL,salt TEXT NOT NULL,password TEXT NOT NULL,legacy_owner INTEGER NOT NULL)')
    db.execute('CREATE TABLE IF NOT EXISTS sessions (token TEXT PRIMARY KEY,user_id TEXT NOT NULL,expires REAL NOT NULL)')
    if 'license_hash' not in [row['name'] for row in db.execute('PRAGMA table_info(users)')]:
        db.execute('ALTER TABLE users ADD COLUMN license_hash TEXT')
    db.execute("CREATE TABLE IF NOT EXISTS licenses (key_hash TEXT PRIMARY KEY,id TEXT UNIQUE NOT NULL,email TEXT NOT NULL,expires REAL,active INTEGER NOT NULL,user_id TEXT)")
    db.execute('DELETE FROM sessions WHERE expires<=?',(time.time(),));db.commit()
    try:
        with db:yield db
    finally:db.close()

def credentials(payload):
    email=payload.get('email');password=payload.get('password')
    if not isinstance(email,str) or len(email)>254 or not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',email.strip()):raise ValueError('Informe um e-mail válido.')
    if not isinstance(password,str) or not 8<=len(password)<=128:raise ValueError('A senha deve ter de 8 a 128 caracteres.')
    return email.strip().casefold(),password

def password_hash(password,salt):
    return hashlib.pbkdf2_hmac('sha256',password.encode(),bytes.fromhex(salt),310000).hex()

def license_hash(key):
    if not isinstance(key,str):raise ValueError('Informe sua chave de licença.')
    key=key.strip().upper()
    if not re.fullmatch(r'APROVA-(?:[0-9A-F]{8}-){3}[0-9A-F]{8}',key):raise ValueError('Chave de licença inválida. Copie a chave completa.')
    return hashlib.sha256(key.encode()).hexdigest()

def issue_license(email='',days=None):
    if not isinstance(email,str) or (email and (len(email)>254 or not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',email.strip()))):raise ValueError('Informe um e-mail válido ou deixe vazio.')
    if days is not None and (type(days) is not int or not 1<=days<=3650):raise ValueError('A validade deve ser de 1 a 3650 dias ou sem prazo.')
    secret=secrets.token_hex(16).upper();key='APROVA-'+'-'.join(secret[i:i+8] for i in range(0,32,8))
    identifier=secrets.token_hex(8);expires=time.time()+days*86400 if days is not None else None
    with connect() as db:
        db.execute('INSERT INTO licenses VALUES (?,?,?,?,?,NULL)',(license_hash(key),identifier,email.strip().casefold(),expires,1))
    return {'key':key,'id':identifier,'email':email.strip().casefold(),'expires':expires}

def activate_license(db,key,user_id,email):
    hashed=license_hash(key);row=db.execute('SELECT * FROM licenses WHERE key_hash=?',(hashed,)).fetchone()
    if not row or not row['active']:raise ValueError('Licença inválida ou desativada.')
    if row['expires'] is not None and row['expires']<=time.time():raise ValueError('Esta licença expirou.')
    if row['email'] and row['email']!=email:raise ValueError('Esta licença pertence a outro e-mail.')
    if row['user_id'] and row['user_id']!=user_id:raise ValueError('Esta licença já foi ativada em outra conta.')
    db.execute('UPDATE licenses SET user_id=? WHERE key_hash=?',(user_id,hashed))
    db.execute('UPDATE users SET license_hash=? WHERE id=?',(hashed,user_id))
    return hashed

def licensed(db,user):
    if not user['license_hash']:return False
    return bool(db.execute('SELECT 1 FROM licenses WHERE key_hash=? AND user_id=? AND active=1 AND (expires IS NULL OR expires>?)',(user['license_hash'],user['id'],time.time())).fetchone())

def revoke_license(identifier):
    with connect() as db:
        row=db.execute('SELECT * FROM licenses WHERE id=?',(identifier.strip(),)).fetchone()
        if not row:
            try:row=db.execute('SELECT * FROM licenses WHERE key_hash=?',(license_hash(identifier),)).fetchone()
            except ValueError:pass
        if not row:raise ValueError('Licença não encontrada.')
        db.execute('UPDATE licenses SET active=0 WHERE key_hash=?',(row['key_hash'],))
        if row['user_id']:db.execute('DELETE FROM sessions WHERE user_id=?',(row['user_id'],))

def list_licenses():
    with connect() as db:
        return [dict(row) for row in db.execute("SELECT licenses.id,licenses.email,licenses.expires,licenses.active,users.email AS activated_email FROM licenses LEFT JOIN users ON users.id=licenses.user_id ORDER BY licenses.id DESC")]

def public(row):
    return {'id':row['id'],'email':row['email'],'name':row['name'],'legacy_owner':bool(row['legacy_owner'])}

def session(db,user):
    token=secrets.token_urlsafe(32)
    db.execute('INSERT INTO sessions VALUES (?,?,?)',(hashlib.sha256(token.encode()).hexdigest(),user['id'],time.time()+TTL));db.commit()
    return {'user':public(user)},f'{COOKIE}={token}; HttpOnly; SameSite=Strict; Path=/; Max-Age={TTL}'

def register(payload):
    email,password=credentials(payload);name=payload.get('name')
    if not isinstance(name,str) or not 1<=len(name.strip())<=80:raise ValueError('Informe seu nome, com até 80 caracteres.')
    salt=secrets.token_hex(16);hashed=password_hash(password,salt)
    with connect() as db:
        db.execute('BEGIN IMMEDIATE')
        owner=not db.execute('SELECT 1 FROM users LIMIT 1').fetchone()
        user_id=secrets.token_hex(16)
        try:db.execute('INSERT INTO users (id,email,name,salt,password,legacy_owner) VALUES (?,?,?,?,?,?)',(user_id,email,name.strip(),salt,hashed,int(owner)))
        except sqlite3.IntegrityError:raise ValueError('Não foi possível cadastrar esse e-mail. Se já possui uma conta, use Entrar.') from None
        activate_license(db,payload.get('license_key'),user_id,email)
        return session(db,db.execute('SELECT * FROM users WHERE email=?',(email,)).fetchone())

def login(payload):
    email,password=credentials(payload)
    with connect() as db:
        db.execute('BEGIN IMMEDIATE')
        row=db.execute('SELECT * FROM users WHERE email=?',(email,)).fetchone()
        salt=row['salt'] if row else '00'*16
        hashed=password_hash(password,salt)
        if not row or not hmac.compare_digest(hashed,row['password']):raise ValueError('E-mail ou senha incorretos.')
        key=payload.get('license_key')
        if key:activate_license(db,key,row['id'],email)
        row=db.execute('SELECT * FROM users WHERE id=?',(row['id'],)).fetchone()
        if not licensed(db,row):raise ValueError('Sua conta precisa de uma licença ativa. Informe uma chave válida para ativar ou renovar.')
        return session(db,row)

def cookie_token(header):
    try:
        cookie=SimpleCookie();cookie.load(header or '')
        return cookie[COOKIE].value if COOKIE in cookie else ''
    except Exception:return ''

def identify(header):
    token=cookie_token(header)
    if not token or len(token)>100:return None
    with connect() as db:
        row=db.execute('SELECT users.* FROM sessions JOIN users ON users.id=sessions.user_id WHERE token=? AND expires>?',(hashlib.sha256(token.encode()).hexdigest(),time.time())).fetchone()
        return public(row) if row and licensed(db,row) else None

def logout(header):
    with connect() as db:db.execute('DELETE FROM sessions WHERE token=?',(hashlib.sha256(cookie_token(header).encode()).hexdigest(),))
    return f'{COOKIE}=; HttpOnly; SameSite=Strict; Path=/; Max-Age=0'

def data_path(original):
    user=CURRENT.get()
    if not user:return original
    directory=(Path(os.environ['APROVA_DATA_DIR'])/user['id'] if os.getenv('APROVA_DATABASE_URL') else original.parent/'account-data'/user['id']);directory.mkdir(parents=True,exist_ok=True)
    destination=directory/original.name
    # Only the first account can receive this installation's pre-login data.
    marker=directory/('.migrated-'+original.name)
    if not os.getenv('APROVA_DATABASE_URL') and user['legacy_owner'] and not marker.exists():
        if not destination.exists() and original.exists():
            if original.is_file():shutil.copy2(original,destination)
            elif original.is_dir():shutil.copytree(original,destination)
        marker.touch()
    return destination

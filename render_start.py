"""Single Render test service supervising HTTP and one queue worker."""
import os, signal, subprocess, sys, time
import auth

def prepare():
    if not os.getenv('APROVA_PUBLIC_URL') and os.getenv('RENDER_EXTERNAL_URL'):os.environ['APROVA_PUBLIC_URL']=os.environ['RENDER_EXTERNAL_URL'].rstrip('/')
    os.environ.setdefault('APROVA_DATA_DIR','/tmp/aprova-accounts')
    from cloud_server import config
    config()
    key=os.getenv('APROVA_INITIAL_LICENSE','').strip()
    if key:
        hashed=auth.license_hash(key)
        with auth.connect() as db:
            db.execute('INSERT INTO licenses VALUES (?,?,?,?,?,NULL) ON CONFLICT(key_hash) DO NOTHING',(hashed,hashed[:16],os.getenv('APROVA_INITIAL_EMAIL','').strip().casefold(),None,1))
    else:
        from cloud_db import connect
        with connect() as db:db.execute('SELECT 1')

def main():
    prepare();children=[];stopping=False
    port=int(os.getenv('PORT','10000'))
    if not 1<=port<=65535:raise ValueError('Porta inválida.')
    def stop(*_):
        nonlocal stopping
        stopping=True
        for child in children:
            if child.poll() is None:child.terminate()
    signal.signal(signal.SIGTERM,stop);signal.signal(signal.SIGINT,stop)
    try:
        children.append(subprocess.Popen([sys.executable,'-m','gunicorn','--bind','0.0.0.0:'+str(port),'--workers','1','--threads','4','--timeout','90','cloud_server:application']))
        children.append(subprocess.Popen([sys.executable,'cloud_worker.py']))
        while not stopping:
            if any(child.poll() is not None for child in children):raise RuntimeError('Um processo encerrou; reiniciando o serviço completo.')
            time.sleep(.5)
    finally:
        stop()
        for child in children:
            try:child.wait(timeout=10)
            except subprocess.TimeoutExpired:child.kill();child.wait()

if __name__=='__main__':main()

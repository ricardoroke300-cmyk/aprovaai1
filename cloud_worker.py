"""One durable job at a time per process. Scale this service for parallelism."""
import json, logging, signal, threading
import auth, cancellation, cloud_store
from cloud_tasks import execute
STOP=threading.Event()

def run_job(job,operation=execute):
    user=cloud_store.user_for_worker(job['user_id'])
    if not user:
        cloud_store.finish(job['id'],job['lease'],error='A licença desta conta não está ativa.')
        return
    user_token=auth.CURRENT.set(user);cancel_token=cancellation.begin(job['id'])
    done=threading.Event()
    def keep_alive():
        while not done.wait(2):
            try:
                active=cloud_store.heartbeat(job['id'],job['lease'],cancellation.stage(job['id']))
                if not active or not cloud_store.user_for_worker(job['user_id']):cancellation.cancel(job['id'])
            except Exception:
                cancellation.cancel(job['id']);return
    thread=threading.Thread(target=keep_alive,daemon=True);thread.start()
    try:
        result,mime=operation(job['path'],job['payload'])
        cancellation.check()
        if not cloud_store.user_for_worker(job['user_id']):raise RuntimeError('A licença desta conta não está ativa.')
        encoded=result if isinstance(result,bytes) else json.dumps(result,ensure_ascii=False).encode()
        cloud_store.finish(job['id'],job['lease'],encoded,mime)
    except (ValueError,RuntimeError) as error:
        cloud_store.finish(job['id'],job['lease'],error=str(error))
    except Exception as error:
        logging.error('Generation worker failure: %s',type(error).__name__)
        cloud_store.finish(job['id'],job['lease'],error='Não foi possível concluir a geração. Tente novamente.')
    finally:
        done.set();thread.join(timeout=3)
        cancellation.finish(job['id'],cancel_token);auth.CURRENT.reset(user_token)

def main():
    from cloud_server import config
    config()
    signal.signal(signal.SIGTERM,lambda *_:STOP.set())
    signal.signal(signal.SIGINT,lambda *_:STOP.set())
    while not STOP.is_set():
        try:
            job=cloud_store.claim()
            if job:run_job(job)
            else:STOP.wait(1)
        except Exception as error:
            logging.error('Queue worker unavailable: %s',type(error).__name__);STOP.wait(3)

if __name__=='__main__':main()

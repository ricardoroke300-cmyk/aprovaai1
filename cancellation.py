"""Cooperative cancellation of local generation requests."""
import threading,time
from contextvars import ContextVar
KEY=ContextVar('generation_key',default='')
STAGES={}
CURRENT=ContextVar('generation_cancel',default=None)
EVENTS={}
CREATED={}
GUARD=threading.Lock()
def event_for(key):
    with GUARD:
        now=time.monotonic()
        for old in list(EVENTS):
            if old not in STAGES and now-CREATED.get(old,now)>300:
                EVENTS.pop(old,None);CREATED.pop(old,None)
        if key not in EVENTS:
            if len(EVENTS)>1000:raise RuntimeError('Muitas solicitações de cancelamento.')
            EVENTS[key]=threading.Event();CREATED[key]=now
        return EVENTS[key]
def begin(key):
    KEY.set(key)
    set_stage('Preparando conteúdo…')
    return CURRENT.set(event_for(key) if key else None)
def finish(key,token):
    CURRENT.reset(token)
    with GUARD:
        EVENTS.pop(key,None)
        STAGES.pop(key,None)
        CREATED.pop(key,None)
    KEY.set('')
def cancel(key):event_for(key).set()
def check():
    event=CURRENT.get()
    if event is not None and event.is_set():raise RuntimeError('Geração cancelada pelo aluno.')

def set_stage(message):
    key=KEY.get()
    if key:
        with GUARD:STAGES[key]=message
def stage(key):
    with GUARD:return STAGES.get(key,'Preparando conteúdo…')

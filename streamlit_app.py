"""aprova.ai on Streamlit Community Cloud with the original HTML interface."""
import logging, os, secrets, threading
from pathlib import Path
import streamlit as st
import streamlit.components.v1 as components

st.set_page_config(page_title='aprova.ai',page_icon='📚',layout='wide',initial_sidebar_state='collapsed')

@st.cache_resource
def runtime(settings):
    for name in ('APROVA_DATABASE_URL','GEMINI_API_KEY','GEMINI_MODEL','APROVA_INITIAL_LICENSE','APROVA_INITIAL_EMAIL'):
        if settings.get(name):os.environ[name]=str(settings[name])
    os.environ['APROVA_PUBLIC_URL']='http://127.0.0.1:8766'
    os.environ['APROVA_WEB_TOKEN']=secrets.token_urlsafe(48)
    os.environ.setdefault('APROVA_DATA_DIR','/tmp/aprova-streamlit')
    from render_start import prepare
    prepare()
    import cloud_store, cloud_worker
    def loop():
        while True:
            try:
                job=cloud_store.claim()
                if job:cloud_worker.run_job(job)
                else:threading.Event().wait(2)
            except Exception as error:
                logging.error('Streamlit worker: %s',type(error).__name__)
                threading.Event().wait(3)
    worker=threading.Thread(target=loop,daemon=True,name='aprova-generation');worker.start()
    return worker

try:
    settings=dict(st.secrets)
    if not all(settings.get(key) for key in ('APROVA_DATABASE_URL','GEMINI_API_KEY','GEMINI_MODEL')):raise ValueError('Configuração incompleta')
    runtime(settings)
except Exception as error:
    logging.error('Streamlit startup: %s',type(error).__name__)
    st.error('Configure APROVA_DATABASE_URL, GEMINI_API_KEY e GEMINI_MODEL em Settings → Secrets. Confira a conexão PostgreSQL e as permissões do banco.')
    st.stop()

st.markdown('<style>.block-container{padding:0.5rem;max-width:100%}footer{display:none}</style>',unsafe_allow_html=True)
component=components.declare_component('aprova_interface',path=str(Path(__file__).parent/'streamlit_component'))
from streamlit_bridge import batch
if 'aprova_bridge' not in st.session_state:st.session_state.aprova_bridge={'responses':[]}
session=st.session_state.aprova_bridge
value=component(responses=session['responses'],key='aprova-interface',default=None)
try:
    replies=batch(value,session)
    if replies is not None:
        session['responses']=replies
        st.rerun()
except (ValueError,TypeError):
    st.error('Não foi possível processar a solicitação. Recarregue a página e entre novamente.')

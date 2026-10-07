# Publicar o aprova.ai no Streamlit Community Cloud

Esta versão mantém a interface HTML como um componente bidirecional do Streamlit. As solicitações passam pela sessão Streamlit e pelo backend Python existente, sem uma segunda porta HTTP pública, Render ou Gunicorn. A fila tem um processador compartilhado dentro do processo Streamlit. O banco é o PostgreSQL do Supabase; Supabase Auth e Storage não são utilizados.

## Preparação

1. Feche INICIAR.bat. Coloque preparar_streamlit.py junto dele e execute. Ele prepara os arquivos e cria uma pasta **aprova-ai-github-streamlit** contendo somente código e documentação de publicação.
2. Execute **configurar_streamlit.py** na pasta original. Informe a senha do banco Supabase, a chave Gemini, o modelo em uso e seu e-mail de teste. Os segredos são digitados no seu computador. Ele cria **secrets_streamlit.toml**. Guarde a licença de teste exibida. Não envie esse arquivo ao GitHub ou ao chat.
3. Substitua no seu repositório o código de publicação pelo **conteúdo** da pasta aprova-ai-github-streamlit. Mantenha a pasta **streamlit_component**, incluindo index.html e app.html; preserve sua estrutura. requirements.txt dessa pasta inclui Streamlit e psycopg. Não use o antigo requirements.txt apenas com ReportLab. Arquivos antigos de Render podem ser removidos do repositório; render_start.py permanece porque contém a rotina de preparação reutilizada.

## Publicação

1. Entre em https://share.streamlit.io e conecte sua conta GitHub.
2. Use Create app, selecione o repositório e a branch onde enviou os arquivos.
3. Em **Main file path**, coloque **streamlit_app.py**.
4. Em **Advanced settings → Secrets**, cole o conteúdo de secrets_streamlit.toml. Selecione Python 3.12, se houver opção. Não precisa definir Start Command ou Build Command.
5. Clique em Deploy e aguarde. Se a configuração estiver incompleta, o aplicativo mostra uma mensagem sem revelar credenciais. Falhas de conexão ou permissão exigem conferir a senha, usuário, host e porta 5432 do Session pooler no Supabase. As tabelas são criadas no schema privado aprova_private, pelo proprietário conectado; não exponha esse schema na Data API.
6. Abra o aplicativo e cadastre seu e-mail, senha e a licença de teste. Caso já tenha cadastrado o mesmo e-mail no banco central, use Entrar; a licença nova pode ativar ou renovar a conta. A licença inicial é criada uma vez e não é reativada após revogação.

## Conferência após publicar

Teste login, importação de edital, questões, simulado, apostila PDF, foto e correção de redação, cancelamento e cronômetro. Confira o progresso após sair e entrar. Recarregar a página pode encerrar a sessão Streamlit e exigir login novamente; o progresso permanece no banco. Aguarde a sincronização antes de fechar e exporte sua cópia se ocorrer conflito entre duas sessões.

A preparação passou pelos testes Python do backend, testes JavaScript do transporte e carregamento no runtime real do Streamlit com banco local de teste. Ainda não foi validada no seu Supabase nem publicada em Community Cloud. A comunicação completa no navegador, downloads e uploads precisam ser conferidos após a publicação; não há teste real com Gemini neste ambiente.

## Limites e dados

O processador gera uma tarefa por vez; alunos adicionais aguardam na fila, com uma geração ativa por aluno. O serviço de hospedagem pode reiniciar ou suspender; tarefas interrompidas não são reenviadas automaticamente ao Gemini. A escala não foi medida e não há capacidade garantida de alunos. A cota do Gemini continua valendo.

Progresso, edital, cache de conteúdo de apostilas e histórico de não repetição ficam no PostgreSQL, separados por conta. Resultados da fila são temporários e expiram após sete dias; baixe PDFs finais. Imagens de redação ficam temporariamente no payload até concluir, falhar ou cancelar. A cópia local permanece no navegador do componente e não se transfere automaticamente para outra instalação ou domínio. Para trazer o progresso do aplicativo local, exporte-o em Configurações e importe-o depois do cadastro online. Contas e licenças locais não são migradas automaticamente.

As variáveis de licença inicial podem ser removidas de Secrets depois da criação; a licença permanece no banco. A administração de outras licenças utiliza licenses.py, no computador do proprietário, com conexão privada ao mesmo banco. Não existe botão público para emitir licenças.

Após publicar e conferir o funcionamento, o endereço HTTPS do Streamlit poderá ser configurado no gerador de EXE online para Windows. A versão online continua precisando de internet; o lançador e a compilação Windows precisam ser testados separadamente.

Referências: https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app ; https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/secrets-management ; https://docs.streamlit.io/develop/api-reference/custom-components/st.components.v1.declare_component

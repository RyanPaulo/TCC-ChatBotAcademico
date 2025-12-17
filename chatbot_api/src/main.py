from fastapi import FastAPI
from .routers import auth, alunos, professores, coordenador, curso, curso_disciplina, disciplina, avaliacao, cronograma, aviso, base_conhecimento, msg_aluno, documento, ia_services, trabalho_academico

# Descrição: Este é o ponto de entrada da API do Chatbot Acadêmico, que gerencia as interações e dados do chatbot integrado ao Teams.
app = FastAPI(
    title="API do Chatbot Acadêmico",
    description="API para gerenciar as interações e dados do chatbot acadêmico integrado ao Teams.",
    version="1.0.0"
)

# Inclui os roteadores no aplicativo principal
app.include_router(auth.router)
app.include_router(alunos.router)
app.include_router(professores.router)
app.include_router(coordenador.router)
app.include_router(curso.router)
app.include_router(curso_disciplina.router)
app.include_router(disciplina.router)
app.include_router(avaliacao.router)
app.include_router(cronograma.router)
app.include_router(aviso.router)
app.include_router(base_conhecimento.router)
app.include_router(msg_aluno.router)
app.include_router(documento.router)
app.include_router(ia_services.router)
app.include_router(trabalho_academico.router)


# **** ENDPOINT RAIZ PARA VERIFICAR SE A API ESTA ONLINE ****
@app.get("/get_boas_vindas", tags=["Root"])
def read_root():
    return  {"message": "Bem-vindo á API do Chatbot Academico!"}
from datetime import datetime
from pydantic import BaseModel, Field
from typing import Optional, List
import uuid

### ESQUEMA DE DADOS 'MENSAGEM DO ALUNO' PARA O CHATBOT ARMAZENAR E USAR COMO BASE DE CONHECIMENTO PARA AS PROXIMAS PERGUNTAS ###

# Schema base com os campos que podem ser criados
class MensagemAlunoBase(BaseModel):
    primeira_pergunta: str
    topico: List[str] = Field(default_factory=list)
    feedback: str
    data_hora: datetime = Field(default_factory=datetime.now)


# Schema para a criação de uma nova mensagem
class MensagemAlunoCreate(MensagemAlunoBase):
    pass


# Schema para representar um registro completo do banco de dados
class MensagemAluno(MensagemAlunoBase):
    id_mensagem: uuid.UUID

    class Config:
        from_attributes = True

# Schema para atualização
class MensagemAlunoUpdate(BaseModel):
    primeira_pergunta: Optional[str] = None
    topico: Optional[List[str]] = None
    feedback: Optional[str] = None
    data_hora: Optional[datetime] = Field(default_factory=datetime.now)
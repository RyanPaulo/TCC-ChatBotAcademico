from datetime import datetime
from pydantic import BaseModel, Field, root_validator
from typing import Optional, List
import uuid


### Esquema de dados 'Base de Conhecimento' para o chatbot acessar ###

# Schema da base com os campos que podem ser criados ou atualizados
class BaseConhecimentoBase(BaseModel):
    nome_arquivo_origem: str
    conteudo_processado: str
    palavra_chave: List[str] = Field(default_factory=list)
    categoria: Optional[str] = None
    status: str = "rascunho"
    id_disciplina: Optional[uuid.UUID] = None
    id_tcc: Optional[uuid.UUID] = None
    id_aps: Optional[uuid.UUID] = None
    id_estagio: Optional[uuid.UUID] = None
    id_hora_complementares: Optional[uuid.UUID] = None
    url_documento: Optional[str] = None


# Esquema para a criado de uma no base de conhecimento
class BaseConhecimentoCreate(BaseConhecimentoBase):
    pass


# Para representar um registro completo do banco de dados
class BaseConhecimento(BaseConhecimentoBase):
    id_conhecimento: uuid.UUID
    criado_em: datetime
    atualizado_em: Optional[datetime] = None

    class Config:
        from_attributes = True


# Esquema para atualizar a base de conhecimento (Todos os campos sao opicional)
class BaseConhecimentoUpdate(BaseModel):
    nome_arquivo_origem: Optional[str] = None
    conteudo_processado: Optional[str] = None
    palavra_chave: Optional[List[str]] = None
    categoria: Optional[str] = None
    status: Optional[str] = None
    url_documento: Optional[str] = None
    id_disciplina: Optional[uuid.UUID] = None
    id_tcc: Optional[uuid.UUID] = None
    id_aps: Optional[uuid.UUID] = None
    id_estagio: Optional[uuid.UUID] = None
    id_hora_complementares: Optional[uuid.UUID] = None

# Schema simples para retornar apenas o URL do documento
class DocumentoURLResponse(BaseModel):
    url_documento: str
    nome_arquivo_origem: Optional[str] = None
from datetime import time
from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List
import uuid


### Esquema de dados 'Coordenador' ###
class CoordenadorBase(BaseModel):
    id_funcional: str
    nome_coordenador: str
    sobrenome_coordenador: str
    email_institucional: EmailStr
    departamento: str
    curso_nomes: Optional[List[str]] = Field(default_factory=list)
    dias_atendimento: Optional[List[str]] = Field(default_factory=list)
    atendimento_hora_inicio: Optional[time] = Field(None, example="00:00")
    atendimento_hora_fim: Optional[time] = Field(None, example="00:00")

class CoordenadorCreate(CoordenadorBase):
    password: str

class Coordenador(CoordenadorBase):
    id: uuid.UUID

    class Config:
        from_attributes = True

class CoordenadorUpdate(BaseModel):
    nome_coordenador: Optional[str] = None
    sobrenome_coordenador: Optional[str] = None
    email_institucional: Optional[EmailStr] = None
    departamento: Optional[str] = None
    curso_nomes: Optional[List[str]] = Field(default_factory=list)
    dias_atendimento: Optional[List[str]] = Field(default_factory=list)
    atendimento_hora_inicio: Optional[time] = Field(None, example="00:00")
    atendimento_hora_fim: Optional[time] = Field(None, example="00:00")
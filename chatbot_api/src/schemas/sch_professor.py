from datetime import time
from pydantic import BaseModel, EmailStr, Field, ConfigDict
from typing import Optional, List
import uuid


### Esquema de dados 'Professor' ###

class ProfessorBase(BaseModel):
    id_funcional: str
    nome_professor: str
    sobrenome_professor: str
    email_institucional: EmailStr
    disciplina_nomes: Optional[List[str]] = Field(default_factory=list)
    dias_atendimento: Optional[List[str]] = Field(default_factory=list)
    atendimento_hora_inicio: Optional[time] = Field(None, example="00:00")
    atendimento_hora_fim: Optional[time] = Field(None, example="00:00")

class ProfessorCreate(ProfessorBase):
    password: str

class Professor(ProfessorBase):
    id: uuid.UUID

    model_config = ConfigDict(
        json_encoders={
            time: lambda t: t.strftime('%H:%M:%S')
        },

        from_attributes = True
    )

class ProfessorUpdate(BaseModel):
    nome_professor: Optional[str] = None
    sobrenome_professor: Optional[str] = None
    email_institucional: Optional[EmailStr] = None
    disciplina_nomes: Optional[List[str]] = Field(default_factory=list)
    dias_atendimento: Optional[List[str]] = Field(default_factory=list)
    atendimento_hora_inicio: Optional[time] = Field(None, example="00:00")
    atendimento_hora_fim: Optional[time] = Field(None, example="00:00")


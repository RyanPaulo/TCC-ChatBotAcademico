from pydantic import BaseModel, Field
from typing import Optional
from datetime import date
from enum import Enum
import uuid

### Esquema de dados 'Trabalho Acadêmico' ###


class TipoTrabalhoEnum(str, Enum):
    tc1 = "TC 1"
    tc2 = "TC 2"
    aps = "APS"
    estagio = "estagio"
    hora_complementar = "horas_complementares"


class TrabalhoAcademicoBase(BaseModel):
    tipo: TipoTrabalhoEnum = Field(..., description="Tipo do trabalho: TC 1, TC 2, APS, estagio ou Hora Complementar")
    tema: str = Field(..., description="Tema do trabalho")
    regras: Optional[str] = Field(None, description="Regras e instruções do trabalho")
    data_entrega: Optional[date] = Field(None, description="Data de entrega do trabalho")
    maximo_integrantes: Optional[int] = Field(
        None, description="Número máximo de integrantes no grupo"
    )
    semestre: str = Field(..., max_length=6, description="Semestre no formato ano.semestre (ex: 2025.1)")

    id_orientador: Optional[uuid.UUID] = Field(None, description="ID do professor orientador (tabela professor)")
    id_coordenador: Optional[uuid.UUID] = Field(None, description="ID do professor coorientador (tabela professor)")
    id_curso: uuid.UUID = Field(..., description="ID do curso (tabela curso)")
    id_disciplina: Optional[uuid.UUID] = Field(
        None, description="ID da disciplina (tabela disciplina)"
    )


class TrabalhoAcademicoCreate(TrabalhoAcademicoBase):
    pass


class TrabalhoAcademico(TrabalhoAcademicoBase):
    id_trabalho: uuid.UUID

    class Config:
        from_attributes = True


class TrabalhoAcademicoUpdate(BaseModel):
    tipo: Optional[TipoTrabalhoEnum] = Field(None, description="Tipo do trabalho: TC 1, TC 2, APS, estagio ou Hora Complementar")
    tema: Optional[str] = None
    regras: Optional[str] = None
    data_entrega: Optional[date] = None
    maximo_integrantes: Optional[int] = None
    semestre: Optional[str] = Field(None, max_length=6, description="Semestre no formato ano.semestre (ex: 2025.1)")
    id_orientador: Optional[uuid.UUID] = None
    id_coordenador: Optional[uuid.UUID] = None
    id_curso: Optional[uuid.UUID] = None
    id_disciplina: Optional[uuid.UUID] = None




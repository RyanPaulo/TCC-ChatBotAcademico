
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import date, time
import uuid


### Esquema de dados 'Avaliacao' ###


from enum import Enum

class TipoAvaliacaoEnum(str, Enum):
    np1 = 'NP1'
    np2 = 'NP2'
    sub = 'SUB'
    exame = 'EXAME'

class AvaliacaoBase(BaseModel):
    tipo_avaliacao: TipoAvaliacaoEnum
    data_prova: date
    hora_inicio: Optional[time] = Field(None, example="00:00")
    hora_fim: Optional[time] = Field(None, example="00:00")
    sala: Optional[str] = None
    conteudo: Optional[str] = Field(None, max_length=250)
    id_disciplina: uuid.UUID
    id_aplicador: Optional[uuid.UUID] = None


class AvaliacaoCreate(AvaliacaoBase):
    pass

class Avaliacao(AvaliacaoBase):
    id_avaliacao: uuid.UUID

    class Config:
        from_attributes = True

class AvaliacaoUpdate(BaseModel):
    tipo_avaliacao: Optional[TipoAvaliacaoEnum] = None
    data_prova: Optional[date] = None
    hora_inicio: Optional[time] = Field(None, example="00:00")
    hora_fim: Optional[time] = Field(None, example="00:00")
    sala: Optional[str] = None
    conteudo: Optional[str] = Field(None, max_length=250)
    id_disciplina: Optional[uuid.UUID] = None
    id_aplicador: Optional[uuid.UUID] = None

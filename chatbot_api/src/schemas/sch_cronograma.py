from datetime import time, date
from pydantic import  BaseModel, Field
from typing import Optional
import uuid


### ESQUEMA DE DADOS 'CRONOGRAMA' ###

class CronogramaBase(BaseModel):
    nome_disciplina: str
    hora_inicio: time = Field(..., example="00:00") # Feild = para criar um molde de preencimento da hora
    hora_fim: time = Field(..., example="00:00")
    periodicidade: str = "semanal"
    id_disciplina: uuid.UUID

    dia_semana: Optional[int] = Field(None, ge=1, le=7)
    tipo_aula: Optional[str] = None
    sala: Optional[int] = None
    andar: Optional[int] = None
    bloco: Optional[str] = None
    data_inicio_semestre: Optional[date] = Field(None, example="0000-00-00") # Feild = para criar um molde de preencimento da data
    data_fim_semestre: Optional[date] = Field(None, example="0000-00-00")


class CronogramaCreate(CronogramaBase):
    pass

class Cronograma(CronogramaBase):
    id_cronograma: uuid.UUID

    class Config:
        from_attributes = True


class CronogramaUpdate(BaseModel):
    nome_disciplina: str
    dia_semana: Optional[int] = Field(None, ge=1, le=7)
    hora_inicio: Optional[time] = Field(None, example="00:00")
    hora_fim: Optional[time] = Field(None, example="00:00")
    tipo_aula: Optional[str] = None
    sala: Optional[int] = None
    andar: Optional[int] = None
    bloco: Optional[str] = None
    periodicidade: Optional[str] = None
    data_inicio_semestre: Optional[date] = Field(None, example="0000-00-00")
    data_fim_semestre: Optional[date] = Field(None, example="0000-00-00")
    id_disciplina: Optional[str] = None

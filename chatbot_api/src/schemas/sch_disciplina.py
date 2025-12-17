from pydantic import BaseModel
from typing import Optional, List
import uuid

### Esquema de dados 'Disciplina' ###

class DisciplinaBase(BaseModel):
    nome_disciplina: str
    codigo: str
    semestre: str
    ementa: Optional[str] = None
    carga_horaria: int


class DisciplinaCreate(DisciplinaBase):
    pass # Pass - por que nao precisa de mais nenhum campo extra alem do DisciplinaBase

class ProfessorInfo(BaseModel):
    nome_professor: str
    sobrenome_professor: str

class DisciplinaEmenta(BaseModel):
    ementa: Optional[str] = None

class Disciplina(DisciplinaBase):
    id_disciplina: uuid.UUID
    # id_curso: uuid.UUID

    professores: List[ProfessorInfo] = []
    tipo_aula: Optional[str] = None

    class Config:
        from_attributes = True

class DisciplinaUpdate(BaseModel):
    nome_disciplina: Optional[str] = None
    codigo: Optional[str] = None
    semestre: Optional[str] = None
    ementa: Optional[str] = None
    carga_horaria: Optional[int] = None



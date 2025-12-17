from datetime import datetime
from pydantic import BaseModel, Field, root_validator
from typing import Optional
import uuid

### Esquema de dados 'Aviso' ###

class AvisoBase(BaseModel):
    titulo: str
    conteudo: str
    data: datetime = Field(..., example="0000-00-00T00:00")
    id_disciplina: Optional[uuid.UUID] = None
    id_professor: Optional[uuid.UUID] = None
    id_coordenador: Optional[uuid.UUID] = None

    @root_validator(pre=True)
    def check_autor_exclusivo(cls, values):
        professor_id = values.get('id_professor')
        coordenador_id = values.get('id_coordenador')

        if (professor_id is not None and coordenador_id is not None):
            raise ValueError("Um aviso deve ser de um professor OU de um coordenador, não de ambos.")

        if (professor_id is None and coordenador_id is None):
            raise ValueError("Um aviso deve ter um autor(professor ou coordenador).")

        return values

class AvisoCreate(AvisoBase):
    pass

class Aviso(AvisoBase):
    id_aviso: uuid.UUID

    class Config:
        from_attributes = True

# Esquema para atualizar a base de conhecimento (todos os campos sao opcionais)
class AvisoUpdate(BaseModel):
    titulo: Optional[str] = None
    conteudo: Optional[str] = None
    data: Optional[datetime] = Field(None, example="0000-00-00T00:00") # example > para editar o formado de edição
    id_disciplina: Optional[uuid.UUID] = None
    id_professor: Optional[uuid.UUID] = None
    id_coordenador: Optional[uuid.UUID] = None
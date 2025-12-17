from pydantic import BaseModel, EmailStr
from typing import Optional
import uuid

### Esquema de dados 'Aluno' ###

# Base com os campos comuns
class AlunoBase(BaseModel):
    matricula_ra: str
    nome_aluno: str
    sobrenome_aluno: str
    email_institucional: EmailStr
    semestre: int
    turma: str
    id_curso: uuid.UUID

# Class para receber dados na criação de um aluno
class AlunoCreate(AlunoBase):
    password: str

# Class para retornar os daos de um aluno (sem senha)
class Aluno(AlunoBase):
    id: uuid.UUID

    class Config:
        from_attributes = True # Permite que o Pydantic leia dados de objetos

# Class para atualizar parametros nao tabela aluno
class AlunoUpdate(BaseModel):
    nome_aluno: Optional[str] = None
    sobrenome_aluno: Optional[str] = None
    email_institucional: Optional[EmailStr] = None
    semestre: Optional[int] = None
    turma: Optional[str] = None
    id_curso: Optional[uuid.UUID] = None

# Class para retornar apenas email e RA do aluno
class AlunoEmailRA(BaseModel):
    email_institucional: EmailStr
    matricula_ra: str

    class Config:
        from_attributes = True

# Class para retornar a quantidade de alunos na mesma turma
class AlunoQuantidadeTurma(BaseModel):
    quantidade_alunos: int
    nome_curso: str
    turma: str
    semestre: int

    class Config:
        from_attributes = True


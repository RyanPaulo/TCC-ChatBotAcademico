from src.schemas.sch_disciplina import Disciplina
from fastapi import APIRouter, HTTPException, status, Depends
from ..supabase_client import supabase
from pydantic import BaseModel
from typing import List
from ..dependencies import require_admin_or_coordenador_or_professor, require_all, require_admin_or_coordenador
import uuid

# --- ROUTER CURSO DISCIPLINA ---

class CursoDisciplinaCreate(BaseModel):
    id_curso: uuid.UUID
    id_disciplina: uuid.UUID

router = APIRouter(
    prefix="/curso-disciplina",
    tags=["Associação Curso-Disciplina"]
)

### ENDPOINT PARA VIRGULA DISCIPLINA AOS CURSOS ###
@router.post("/", status_code=status.HTTP_201_CREATED)
def create_disciplina_a_curso(association_data: CursoDisciplinaCreate, current_user: dict = Depends(require_admin_or_coordenador_or_professor)):
    try:
        payload = {
            "id_curso": str(association_data.id_curso),
            "id_disciplina": str(association_data.id_disciplina)
        }

        # Cria a associação na tabela CursoDisciplina
        db_response = supabase.table("cursodisciplina").insert(payload).execute()

        if not db_response.data:
            raise HTTPException(status_code=500, detail="Erro ao associar disciplina ao curso.")

        # Busca todos os alunos do curso
        alunos_response = supabase.table("aluno").select("id").eq("id_curso", payload['id_curso']).execute()

        if alunos_response.data:
            # Prepara e insere as matrículas na tabela AlunoDisciplina
            matriculas_para_criar = [
                {"id_aluno": aluno['id'], "id_disciplina": payload['id_disciplina']}
                for aluno in alunos_response.data
            ]
            if matriculas_para_criar:
                supabase.table("alunodisciplina").insert(matriculas_para_criar).execute()

        return db_response.data[0]

    except Exception as e:
        # Tratamento de erro para chaves duplicadas
        if "duplicate key value violates unique constraint" in str(e).lower():
            raise HTTPException(status_code=409, detail="Esta disciplina já está associada a este curso.")
        raise HTTPException(status_code=400, detail=str(e))

### ENDPOINT PARA LISTAR DISCIPLINAS DE UM CURSO ESPECÍFICO ###
@router.get("/lista_disciplina/{id_curso}", response_model=List[Disciplina])
def get_disciplinas_by_curso(id_curso: uuid.UUID, current_user: dict = Depends(require_all)):
    try:
        response = supabase.table("cursodisciplina").select(
            "disciplina!cursodisciplina_id_disciplina_fkey(*)"
        ).eq(
            "id_curso", str(id_curso)
        ).execute()

        if not response.data:
            return []


        disciplinas_list = [item['disciplina'] for item in response.data]

        return disciplinas_list

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Um erro inesperado ocorreu: {str(e)}")

### ENDPOINT PARA DELETAR AS ASSOCIAÇOES ###
@router.delete("/detele/{id_curso}/{id_disciplina}", status_code=status.HTTP_204_NO_CONTENT)
def delete_disciplina_of_curso(id_curso: uuid.UUID, id_disciplina: uuid.UUID, current_user: dict = Depends(require_admin_or_coordenador_or_professor)):
    try:
        # Busca todos os alunos do curso que serão afetados
        response = supabase.table("aluno").select("id").eq("id_curso", str(id_curso)).execute()

        if response.data:
            # Prepara uma lista de IDs dos alunos para a cláusula 'in'
            ids_alunos_afetados = [aluno['id'] for aluno in response.data]

            # Remove as matrículas da tabela AlunoDisciplina que correspondem
            if ids_alunos_afetados:
                supabase.table("alunodisciplina").delete().eq(
                    "id_disciplina", str(id_disciplina)
                ).in_(
                    "id_aluno", ids_alunos_afetados
                ).execute()

        # Remove a associação principal da tabela CursoDisciplina
        db_response = supabase.table("cursodisciplina").delete().match({
            "id_curso": str(id_curso),
            "id_disciplina": str(id_disciplina)
        }).execute()

        # Se a resposta não contiver dados, significa que a associação não existia.
        if not db_response.data:
            raise HTTPException(status_code=404, detail="Associação entre curso e disciplina não encontrada.")

        return
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


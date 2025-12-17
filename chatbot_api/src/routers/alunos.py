from fastapi import APIRouter, HTTPException, status, Depends
from typing import List
from ..supabase_client import supabase
from ..schemas.sch_aluno import AlunoCreate, Aluno, AlunoUpdate, AlunoEmailRA, AlunoQuantidadeTurma
from ..dependencies import require_admin_or_coordenador, require_all, require_admin_or_coordenador_or_professor
import uuid

# --- ROUTER ALUNOS ---

router = APIRouter(
    prefix="/alunos", # Definir coordenadas do URL
    tags=["Alunos"]
)

### ENDPOINT PARA CASDATRAR ALUNO ###
@router.post("/", status_code=status.HTTP_201_CREATED, response_model=Aluno)
def create_aluno(aluno_data: AlunoCreate, current_user: dict = Depends(require_admin_or_coordenador_or_professor)): 
    try:
        # Criar o usuario no Supabase Auth
        auth_response = supabase.auth.sign_up({
            "email": aluno_data.email_institucional,
            "password": aluno_data.password,
            "options": {
                "data": {
                    "name": f"{aluno_data.nome_aluno} {aluno_data.sobrenome_aluno}",
                    "role": "aluno"
                }
            }
        })
        user_id = auth_response.user.id

        # Prepara os dados do aluno ser adiconado na tabela "Aluno"
        aluno_profile_data = aluno_data.model_dump(exclude={"password"})
        aluno_profile_data["id"] = user_id
        aluno_profile_data['id_curso'] = str(aluno_profile_data['id_curso'])

        # Inserir o perfil do aluno na tabela Aluno
        db_response = supabase.table("aluno").insert(aluno_profile_data).execute()

        # Verifica se a inserção foi bem-sucedida
        if not db_response.data:
            raise HTTPException(status_code=500, detail="Erro ao salvar o perfil do aluno.")

        new_aluno = db_response.data[0]
        id_new_aluno = new_aluno['id']
        id_curso_aluno = new_aluno['id_curso']

        # Buscar os IDs das disciplinas do curso na tabela associativa "CursoDisciplina"
        disciplinas_response = supabase.table("cursodisciplina").select("id_disciplina").eq("id_curso", id_curso_aluno).execute()

        if disciplinas_response.data:
            # Preparar os registros para a tabela AlunoDisciplina
            create_registration = [
                {"id_aluno": id_new_aluno,  "id_disciplina": item['id_disciplina']}
                for item in disciplinas_response.data
            ]

            # Inserir todas as matrículas de uma vez
            if create_registration:
                supabase.table("alunodisciplina").insert(create_registration).execute()

        return new_aluno

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


### ENDPOINT PARA BUSCAR UM ALUNO PELO EMAIL ###
@router.get("/get_email/{email}", response_model=AlunoEmailRA)
def get_aluno_by_email(email: str): #, current_user: dict = Depends(require_all) 
    try:
        # Realiza a consulta na tabela "aluno" filtrando pelo email_institucional
        # Retorna apenas email_institucional e matricula_ra
        response = supabase.table("aluno").select("email_institucional, matricula_ra").eq("email_institucional", email).single().execute()

        # Verifica se a busca retornou algum dado
        if not response.data:
            # Se não retornou, o aluno não foi encontrado. Lançamos um erro 404.
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Nenhum aluno encontrado com o email '{email}'."
            )

        # Se encontrou, retorna apenas email_institucional e matricula_ra.
        return response.data

    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Um erro inesperado ocorreu: {str(e)}"
        )

### ENDPOINT PARA CONSULTAR QUANTIDADE DE ALUNOS NA MESMA TURMA ###
@router.get("/get_quantidade_turma/{id_aluno}", response_model=AlunoQuantidadeTurma)
def get_quantidade_alunos_turma(id_aluno: uuid.UUID, current_user: dict = Depends(require_all)):
    try:
        # Busca o aluno pelo id para obter turma, curso e semestre
        aluno_response = supabase.table("aluno").select("turma, id_curso, semestre").eq("id", str(id_aluno)).single().execute()
        
        if not aluno_response.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Aluno com ID '{id_aluno}' não encontrado."
            )
        
        turma_aluno = aluno_response.data['turma']
        id_curso_aluno = aluno_response.data['id_curso']
        semestre_aluno = aluno_response.data['semestre']
        
        # Busca o nome do curso
        curso_response = supabase.table("curso").select("nome_curso").eq("id_curso", str(id_curso_aluno)).single().execute()
        
        if not curso_response.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Curso com ID '{id_curso_aluno}' não encontrado."
            )
        
        nome_curso = curso_response.data['nome_curso']
        
        # Conta quantos alunos têm a mesma turma e curso
        count_response = supabase.table("aluno").select("id", count="exact").eq("turma", turma_aluno).eq("id_curso", str(id_curso_aluno)).execute()
        
        # Usa o atributo count se disponível, caso contrário conta os dados retornados
        quantidade = count_response.count if hasattr(count_response, 'count') and count_response.count is not None else len(count_response.data) if count_response.data else 0
        
        return {
            "quantidade_alunos": quantidade,
            "nome_curso": nome_curso,
            "turma": turma_aluno,
            "semestre": semestre_aluno
        }
    
    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Um erro inesperado ocorreu: {str(e)}"
        )

### ENDPOINT PARA LISTAR TODOS OS ALUNOS CADASTRADOS NO BD ###
@router.get("/get_list_alunos/", response_model=List[Aluno])
def get_all_aluno(current_user: dict = Depends(require_all)):  
    try:
        response = supabase.table("aluno").select("*").execute()
        return response.data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

### ENDPOINT PARA ATUALIZAR UM ALUNO ###
# Utilizando o RA do aluno como referencia o RA do aluno
@router.put("/update/{ra}", response_model=Aluno)
def update_aluno(ra: str, aluno_update_data: AlunoUpdate, current_user: dict = Depends(require_admin_or_coordenador)): 
    try:
        # Cria um dicionario apensa com os dados que foram enviados (nâo none)
        update_payload = aluno_update_data.model_dump(exclude_unset=True)

        #  Buscamos o aluno ANTES de atualizar para saber o curso antigo
        aluno_response = supabase.table("aluno").select("id, id_curso").eq("matricula_ra", ra).single().execute()
        if not aluno_response.data:
            raise HTTPException(status_code=404, detail="Aluno nao encontrado.")

        id_aluno = aluno_response.data['id']
        id_curso_previous = aluno_response.data['id_curso']

        # Verificamos se o curso do aluno está sendo alterado
        new_id_curso = update_payload.get('id_curso', id_curso_previous)
        if isinstance(new_id_curso, uuid.UUID):
            new_id_curso = str(new_id_curso)

        # Atualiza os dados principais do aluno
        if 'id_curso' in update_payload:
            update_payload['id_curso'] = new_id_curso

        db_response = supabase.table('aluno').update(update_payload).eq('id', id_aluno).execute()
        if not db_response.data:
            raise HTTPException(status_code=500, detail="Falha ao atualizar os dados do aluno.")
        aluno_updated = db_response.data[0]

        #Se o curso mudou, sincronizamos as matrículas
        if new_id_curso != id_curso_previous:
            # DELETE: Remove todas as matrículas antigas do aluno
            supabase.table("alunodisciplina").delete().eq("id_aluno", id_aluno).execute()

            # SELECT & INSERT: Busca as disciplinas do novo curso e cria as novas matrículas
            disciplinas_response = supabase.table("disciplina").select("id_disciplina").eq("id_curso", new_id_curso).execute()
            if disciplinas_response.data:
                ra_to_create = [
                    {"id_aluno": id_aluno, "id_disciplina": disciplina['id_disciplina']}
                    for disciplina in disciplinas_response.data
                ]
                if ra_to_create:
                    supabase.table("alunodisciplina").insert(ra_to_create).execute()

        return aluno_updated
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

### ENDPOINT PARA DELETAR UM ALUNO ###
@router.delete("/delete/{ra}", status_code=status.HTTP_204_NO_CONTENT)
def delete_aluno(ra: str, current_user: dict = Depends(require_admin_or_coordenador_or_professor)):
    # ** Lembrar que essa função não remove o usuário do sistema de autenticação do Supabase.
    try:
        # Executa o delete no Supabase | tabela = aluno | indentificado do aluno = matricula_ra
        response = supabase.table("aluno").select("id").eq("matricula_ra", ra).execute()

        # Verifica se algum dado foi retornado (o que segnifica que algo foi deletado)
        if not response.data:
            raise HTTPException(status_code=404, detail="Aluno nao encontrado para deletar.")

        aluno_id = response.data[0]['id']

        delete_response = supabase.table('aluno').delete().eq('id', aluno_id).execute()

        if not delete_response.data:
            raise HTTPException(status_code=500, detail="Falha ao deletar o perfil do aluno. A operação foi abortada.")

        auth_delete_response = supabase.auth.admin.delete_user(aluno_id)

        # HTTP 204 nao deve retornar nenhum corpo de resposta
        return

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))





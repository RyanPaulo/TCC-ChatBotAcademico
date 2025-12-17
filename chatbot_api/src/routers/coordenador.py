from fastapi import APIRouter, HTTPException, status, Depends
from typing import List
import re
import requests
from src.supabase_client import supabase
from src.schemas.sch_coordenador import CoordenadorCreate, Coordenador, CoordenadorUpdate
from ..dependencies import require_admin_or_coordenador, require_all, require_admin_or_coordenador_or_professor
from ..config import settings

# --- ROUTER COORDENADOR ---

router = APIRouter(
    prefix="/coordenador",
    tags=["Coordenador"]
)

### ENDPOINT PARA CADASTRAR COORDENADOR ###
@router.post("/", status_code=status.HTTP_201_CREATED, response_model=Coordenador)
def create_coordenador(coordenador_data: CoordenadorCreate, current_user: dict = Depends(require_admin_or_coordenador_or_professor)):
    user_id = None
    try:
        auth_response = supabase.auth.sign_up({
            "email": coordenador_data.email_institucional,
            "password": coordenador_data.password,
            "options": {
                "data": {
                    "name": f"{coordenador_data.nome_coordenador} {coordenador_data.sobrenome_coordenador}",
                    "role": "coordenador"
                }
            }
        })
        user_id = auth_response.user.id

        # Preparar os dados do coordenador para inserir na tabela "Coordenador"
        coordenador_profile_data = coordenador_data.model_dump(exclude={"password", "curso_nomes"})
        coordenador_profile_data["id"] = user_id

        # Para converter os time
        coordenador_profile_data['atendimento_hora_inicio'] = coordenador_profile_data['atendimento_hora_inicio'].isoformat()
        coordenador_profile_data['atendimento_hora_fim'] = coordenador_profile_data['atendimento_hora_fim'].isoformat()

        # Inserir o perfil do Coordenador na tabela "Coordenador"
        db_response = supabase.table("coordenador").insert(coordenador_profile_data).execute()

        # Verificar se o processo foi bem sucedido
        if not db_response.data:
            raise HTTPException(status_code=500, detail="Erro ao salvar o perfil do coordenador")

        if coordenador_data.curso_nomes:
            curso_ids_response = supabase.table("curso").select("id_curso", "nome_curso").in_("nome_curso", coordenador_data.curso_nomes).execute()

            curso_encontrado = curso_ids_response.data
            if len(curso_encontrado) != len(coordenador_data.curso_nomes):
                # Identificar qual curso não foi encontrado para um erro mais claro
                nomes_encontrado = {d['nome_curso'] for d in curso_encontrado}
                missing_names = [name for name in coordenador_data.curso_nomes if name not in nomes_encontrado]
                raise HTTPException(status_code=404,
                                    detail=f"As seguintes curso não foi encontrado: {', '.join(missing_names)}")

            # Preparar os registros para a tabela associativa
            associations_to_create = [
                {"id_coordenador": user_id, "id_curso": curso['id_curso']}
                for curso in curso_encontrado
            ]

            # Inserir todas as associações de uma vez
            if associations_to_create:
                supabase.table("coordenadorcurso").insert(associations_to_create).execute()

        created_coordenador_dict = db_response.data[0]
        
        coordenador_obj = Coordenador.model_validate(created_coordenador_dict)
        return coordenador_obj


    except Exception as e:
        # Se algo deu errado após a criação do usuário no Auth, tenta deletar o usuário
        if user_id:
            try:
                # Usa a API REST diretamente com service key para deletar o usuário
                delete_url = f"{settings.SUPABASE_URL}/auth/v1/admin/users/{user_id}"
                headers = {
                    "apikey": settings.SUPABASE_SERVICE_KEY,
                    "Authorization": f"Bearer {settings.SUPABASE_SERVICE_KEY}",
                    "Content-Type": "application/json"
                }
                requests.delete(delete_url, headers=headers)
            except Exception as admin_exc:
                print(f"ERRO CRITICO: Falha ao fazer rollback do usuario {user_id}. Erro: {admin_exc}")
                # Não levanta exceção aqui para não mascarar o erro original
        
        if "User already registered" in str(e) or "already registered" in str(e).lower():
            raise HTTPException(status_code=409, detail="Este e-mail ja esta cadastrado.")

        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=400, detail=str(e))



### ENDPOINT PARA LISTAR TODOS OS ALUNOS CADASTRADOS NO BD ###
@router.get("/get_list_coordenador/", response_model=List[Coordenador])
def get_all_aluno(current_user: dict = Depends(require_all)):
    try:
        response = supabase.table("coordenador").select("*").execute()
        return response.data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

### ENDPOINT PARA BUSCAR COORDENADOR PELO NOME ###
@router.get("/get_nome/{nome}", response_model=List[Coordenador])
def get_coordenador_by_nome(nome: str, current_user: dict = Depends(require_all)):
    try:
        # Realiza a consulta na tabela "coordenador" filtrando pelo nome_coordenador (busca parcial e case-insensitive)
        response = supabase.table("coordenador").select("*").ilike("nome_coordenador", f"%{nome}%").execute()

        # Verifica se a busca retornou algum dado
        if not response.data:
            # Se não retornou, o coordenador não foi encontrado. Lançamos um erro 404.
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Nenhum coordenador encontrado com o nome '{nome}'."
            )

        # Se encontrou, retorna os dados dos coordenadores.
        return response.data

    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Um erro inesperado ocorreu: {str(e)}"
        )

### ENDPOINT PARA ATUALIZAR COORDENADOR ###
@router.put("/update/{id}", response_model=Coordenador)
def update_coordenador(id: str, coordenador_update_data: CoordenadorUpdate, current_user: dict = Depends(require_admin_or_coordenador)):
    try:
        # Verificar se o id é um UUID (tem hífens e formato UUID) ou id_funcional
        uuid_pattern = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', re.IGNORECASE)
        
        if uuid_pattern.match(id):
            # Se for UUID, busca diretamente pelo id
            coordenador_response = supabase.table('coordenador').select("id").eq('id', id).execute()
        else:
            # Se não for UUID, busca pelo id_funcional
            coordenador_response = supabase.table('coordenador').select("id").eq('id_funcional', id).execute()
        
        if not coordenador_response.data:
            raise HTTPException(status_code=404, detail="Coordenador não encontrado para atualização.")
        
        coordenador_id = coordenador_response.data[0]['id']
        
        # Preparar o payload excluindo curso_nomes (que não vai na tabela coordenador)
        update_payload = coordenador_update_data.model_dump(exclude_unset=True, exclude={"curso_nomes"})

        if 'atendimento_hora_inicio' in update_payload:
            update_payload['atendimento_hora_inicio'] = update_payload['atendimento_hora_inicio'].isoformat()

        if 'atendimento_hora_fim' in update_payload:
            update_payload['atendimento_hora_fim'] = update_payload['atendimento_hora_fim'].isoformat()

        if not update_payload and not coordenador_update_data.curso_nomes:
            raise HTTPException(status_code=400, detail="Nenhum dado fornecido para atualização.")

        # Atualizar os dados do coordenador (se houver algo para atualizar)
        if update_payload:
            # Usar coordenador_id (UUID) para atualizar, que já foi obtido acima
            response = supabase.table('coordenador').update(update_payload).eq('id', coordenador_id).execute()

            if not response.data:
                raise HTTPException(status_code=404, detail="Coordenador não encontrado para atualização.")
        else:
            # Se não houver dados para atualizar na tabela principal, buscar o coordenador atual
            response = supabase.table('coordenador').select("*").eq('id', coordenador_id).execute()

        # Atualizar associações de cursos se curso_nomes foi fornecido
        if coordenador_update_data.curso_nomes is not None:
            # Deletar associações antigas
            supabase.table("coordenadorcurso").delete().eq("id_coordenador", str(coordenador_id)).execute()
            
            # Buscar os IDs dos cursos pelo nome
            curso_ids_response = supabase.table("curso").select("id_curso", "nome_curso").in_("nome_curso", coordenador_update_data.curso_nomes).execute()
            
            curso_encontrado = curso_ids_response.data
            if len(curso_encontrado) != len(coordenador_update_data.curso_nomes):
                # Identificar qual curso não foi encontrado
                nomes_encontrado = {c['nome_curso'] for c in curso_encontrado}
                missing_names = [name for name in coordenador_update_data.curso_nomes if name not in nomes_encontrado]
                raise HTTPException(status_code=404,
                                    detail=f"As seguintes cursos não foram encontrados: {', '.join(missing_names)}")
            
            # Criar novas associações
            if curso_encontrado:
                associations_to_create = [
                    {"id_coordenador": coordenador_id, "id_curso": curso['id_curso']}
                    for curso in curso_encontrado
                ]
                supabase.table("coordenadorcurso").insert(associations_to_create).execute()

        return response.data[0]
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=str(e))

### ENDPOINT PARA DELETAR COORDENADOR ###
@router.delete("/delete/{id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_coordenador(id: str, current_user: dict = Depends(require_admin_or_coordenador)):
    try:
        response = supabase.table('coordenador').select("id").eq('id_funcional', id).execute()

        if not response.data:
            raise HTTPException(status_code=404, detail="Coordenador não encontrado para deletar.")

        coordenador_id = response.data[0]['id']

        # Deletar avisos relacionados ao coordenador primeiro (para evitar violação de constraint)
        supabase.table("aviso").delete().eq("id_coordenador", str(coordenador_id)).execute()

        # Deletar associações na tabela coordenadorcurso
        supabase.table("coordenadorcurso").delete().eq("id_coordenador", str(coordenador_id)).execute()

        # Deletar o perfil do coordenador
        delete_response = supabase.table('coordenador').delete().eq('id', coordenador_id).execute()

        if not delete_response.data:
            raise HTTPException(status_code=500, detail="Falha ao deletar o perfil do coordenador. A operação foi abortada.")

        # Deletar o usuário do Auth usando API REST
        try:
            delete_url = f"{settings.SUPABASE_URL}/auth/v1/admin/users/{coordenador_id}"
            headers = {
                "apikey": settings.SUPABASE_SERVICE_KEY,
                "Authorization": f"Bearer {settings.SUPABASE_SERVICE_KEY}",
                "Content-Type": "application/json"
            }
            requests.delete(delete_url, headers=headers)
        except Exception as auth_exc:
            print(f"AVISO: Falha ao deletar usuário do Auth: {auth_exc}")
            # Não levanta exceção aqui para não abortar a operação
        
        return None

    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=str(e))


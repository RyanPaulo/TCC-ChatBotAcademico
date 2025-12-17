from fastapi import APIRouter, HTTPException, status, Depends
from ..supabase_client import supabase
from ..schemas.sch_professor import ProfessorCreate, Professor, ProfessorUpdate
from ..dependencies import require_admin_or_coordenador, require_all, require_admin_or_coordenador_or_professor
from ..config import settings
from typing import List
import requests
import re

# --- ROUTER PROFESSORES ---

router = APIRouter(
    prefix="/professores",
    tags=["Professores"]
)

### ENDPOINT PARA CADASTRAR PROFESSOR ###
@router.post("/", status_code=status.HTTP_201_CREATED, response_model=Professor)
def create_professor(professor_data: ProfessorCreate, current_user: dict = Depends(require_admin_or_coordenador_or_professor)):
    user_id = None
    try:
        # Criar o usuario no Supabase Auth
        auth_response = supabase.auth.sign_up({
            "email": professor_data.email_institucional,
            "password": professor_data.password,
            "options": {
                "data": {
                    "name": f"{professor_data.nome_professor} {professor_data.sobrenome_professor}",
                    "role": "professor"
                }
            }
        })
        user_id = auth_response.user.id

        # Prepara os dados do professor ser adiconado na tabela "Professor"
        professor_profile_data = professor_data.model_dump(exclude={"password", "disciplina_nomes"})
        professor_profile_data["id"] = user_id

        # Converte os campos de tempo para o formato ISO
        if professor_profile_data.get('atendimento_hora_inicio'):
            professor_profile_data['atendimento_hora_inicio'] = professor_profile_data['atendimento_hora_inicio'].isoformat()
        if professor_profile_data.get('atendimento_hora_fim'):
            professor_profile_data['atendimento_hora_fim'] = professor_profile_data['atendimento_hora_fim'].isoformat()

        # Inserir o perfil do professor na tabela Professor
        db_response = supabase.table("professor").insert(professor_profile_data).execute()

        # Verifica se a inserção foi bem-sucedida
        if not db_response.data:
            raise HTTPException(status_code=500, detail="Erro ao salvar o perfil do professor.")

        # Associar disciplinas ao professor na tabela associativa
        if professor_data.disciplina_nomes:
            # Buscar os IDs das disciplinas pelo nome
            disciplinas_ids_response = supabase.table("disciplina").select("id_disciplina", "nome_disciplina").in_("nome_disciplina", professor_data.disciplina_nomes).execute()

            disciplinas_encontrada = disciplinas_ids_response.data
            if len(disciplinas_encontrada) != len(professor_data.disciplina_nomes):
                # Identificar qual disciplina não foi encontrada para um erro mais claro
                nomes_encontrado = {d['nome_disciplina'] for d in disciplinas_encontrada}
                missing_names = [name for name in professor_data.disciplina_nomes if name not in nomes_encontrado]
                raise HTTPException(status_code=404,
                                    detail=f"As seguintes disciplinas não foram encontradas: {', '.join(missing_names)}")

            # Preparar os registros para a tabela associativa "ProfessorDisciplina"
            associations_to_create = [
                {"id_professor": user_id, "id_disciplina": disciplina['id_disciplina']}
                for disciplina in disciplinas_encontrada
            ]

            # Inserir todas as associações de uma vez
            if associations_to_create:
                supabase.table("professordisciplina").insert(associations_to_create).execute()

        created_professor_dict = db_response.data[0]

        professor_obj = Professor.model_validate(created_professor_dict)
        return professor_obj

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
            raise HTTPException(status_code=409, detail="Este e-mail já está cadastrado.")

        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=400, detail=str(e))

### ENDPOINT PARA LISTAR TODOS OS PROFESSORES CADASTRADOS NO BD ###
@router.get("/lista_professores/", response_model=List[Professor])
def get_all_professores(current_user: dict = Depends(require_all)):
    try:
        # Realiza a consulta na tabela "professor"
        response = supabase.table("professor").select("*").execute()
        
        print(f"[DEBUG] Total de professores retornados: {len(response.data) if response.data else 0}")
        
        # Busca todas as associações professordisciplina com nomes das disciplinas
        pd_response = supabase.table("professordisciplina").select(
            """
            id_professor,
            disciplina!inner(id_disciplina, nome_disciplina)
            """
        ).execute()
        
        # Cria um dicionário para mapear professor_id -> lista de nomes de disciplinas
        professor_disciplinas_map = {}
        if pd_response.data:
            for pd in pd_response.data:
                prof_id = str(pd.get('id_professor', ''))
                disciplina_info = pd.get('disciplina')
                if disciplina_info and isinstance(disciplina_info, dict):
                    nome_disciplina = disciplina_info.get('nome_disciplina', '')
                    if nome_disciplina:
                        if prof_id not in professor_disciplinas_map:
                            professor_disciplinas_map[prof_id] = []
                        if nome_disciplina not in professor_disciplinas_map[prof_id]:
                            professor_disciplinas_map[prof_id].append(nome_disciplina)
        
        professores_formatados = []
        for prof in response.data:
            prof_id = str(prof.get('id', ''))
            disciplina_nomes = professor_disciplinas_map.get(prof_id, [])
            prof['disciplina_nomes'] = disciplina_nomes
            professores_formatados.append(Professor.model_validate(prof))
        
        return [p.model_dump() for p in professores_formatados]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

### ENDPOINT PARA BUSCAR PROFESSOR POR ID ###
@router.get("/get_professor/{professor_id}", response_model=Professor)
def get_professor_by_id(professor_id: str):
    try:
        # Verificar se o id é um UUID ou id_funcional
        uuid_pattern = r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
        is_uuid = bool(re.match(uuid_pattern, professor_id, re.IGNORECASE))
        
        # Realiza a consulta na tabela "professor" filtrando pelo id ou id_funcional
        if is_uuid:
            response = supabase.table("professor").select("*").eq('id', professor_id).single().execute()
        else:
            response = supabase.table("professor").select("*").eq('id_funcional', professor_id).single().execute()
        
        # Verifica se a busca retornou algum dado
        if not response.data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Professor não encontrado.")
        
        prof = response.data
        prof_id = str(prof.get('id', ''))
        
        # Busca disciplinas associadas diretamente da tabela professordisciplina
        pd_response = supabase.table("professordisciplina").select(
            """
            disciplina!inner(id_disciplina, nome_disciplina)
            """
        ).eq('id_professor', prof_id).execute()
        
        # Processar as disciplinas associadas ao professor
        disciplina_nomes = []
        if pd_response.data:
            for pd in pd_response.data:
                disciplina_info = pd.get('disciplina')
                if disciplina_info and isinstance(disciplina_info, dict):
                    nome = disciplina_info.get('nome_disciplina', '')
                    if nome and nome not in disciplina_nomes:
                        disciplina_nomes.append(nome)
        
        prof['disciplina_nomes'] = disciplina_nomes
        
        return Professor.model_validate(prof)
    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Um erro inesperado ocorreu: {str(e)}"
        )

### ENDPOINT PARA BUSCAR PROFESSOR PELO NOME ###
@router.get("/get_nome/{nome}", response_model=List[Professor])
def get_professor_by_nome(nome: str, current_user: dict = Depends(require_all)):
    try:
        # Realiza a consulta na tabela "professor" filtrando pelo nome_professor (busca parcial e case-insensitive)
        response = supabase.table("professor").select("*").ilike("nome_professor", f"%{nome}%").execute()

        # Verifica se a busca retornou algum dado
        if not response.data:
            # Se não retornou, o professor não foi encontrado. Lançamos um erro 404.
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Nenhum professor encontrado com o nome '{nome}'."
            )

        # Busca todas as associações professordisciplina para os professores encontrados na tabela associativa
        professor_ids = [str(p.get('id', '')) for p in response.data if p.get('id')]
        professor_disciplinas_map = {}
        
        if professor_ids:
            pd_response = supabase.table("professordisciplina").select(
                """
                id_professor,
                disciplina!inner(id_disciplina, nome_disciplina)
                """
            ).in_('id_professor', professor_ids).execute()
            
            if pd_response.data:
                for pd in pd_response.data:
                    prof_id = str(pd.get('id_professor', ''))
                    disciplina_info = pd.get('disciplina')
                    if disciplina_info and isinstance(disciplina_info, dict):
                        nome_disciplina = disciplina_info.get('nome_disciplina', '')
                        if nome_disciplina:
                            if prof_id not in professor_disciplinas_map:
                                professor_disciplinas_map[prof_id] = []
                            if nome_disciplina not in professor_disciplinas_map[prof_id]:
                                professor_disciplinas_map[prof_id].append(nome_disciplina)

        # Processa cada professor e adiciona suas disciplinas
        professores_formatados = []
        for prof in response.data:
            prof_id = str(prof.get('id', ''))
            disciplina_nomes = professor_disciplinas_map.get(prof_id, [])
            prof['disciplina_nomes'] = disciplina_nomes
            
            professores_formatados.append(Professor.model_validate(prof))

        return [p.model_dump() for p in professores_formatados]

    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Um erro inesperado ocorreu: {str(e)}"
        )

### ENDPOINT PARA ATUALIZAR UM PROFESSOR ###
@router.put("/update/{id}", response_model=Professor)
def update_professor(id: str, professor_update_data: ProfessorUpdate, current_user: dict = Depends(require_admin_or_coordenador)):
    try:
        # Cria um dicionario apensa com os dados que foram enviados (não none)
        update_payload = professor_update_data.model_dump(exclude_unset=True)

        # Extrair disciplina_nomes se presente (não vai para a tabela professor diretamente)
        disciplina_nomes = update_payload.pop('disciplina_nomes', None)

        # Converte os campos de tempo para o formato ISO
        if 'atendimento_hora_inicio' in update_payload:
            update_payload['atendimento_hora_inicio'] = update_payload['atendimento_hora_inicio'].isoformat()

        if 'atendimento_hora_fim' in update_payload:
            update_payload['atendimento_hora_fim'] = update_payload['atendimento_hora_fim'].isoformat()

        # Verificar se o id é um UUID (tem hífens e formato UUID) ou id_funcional
        uuid_pattern = r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
        is_uuid = bool(re.match(uuid_pattern, id, re.IGNORECASE))
        
        # Buscar o ID real do professor (UUID) antes de atualizar
        if is_uuid:
            professor_check = supabase.table("professor").select("id").eq('id', id).execute()
        else:
            professor_check = supabase.table("professor").select("id").eq('id_funcional', id).execute()
        
        if not professor_check.data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Professor não encontrado para atualização.")
        
        professor_uuid = professor_check.data[0]['id']
        
        # Atualiza os dados principais do professor
        if update_payload:
            response = supabase.table('professor').update(update_payload).eq('id', professor_uuid).execute()
            if not response.data:
                raise HTTPException(status_code=500, detail="Falha ao atualizar os dados do professor.")
        
        # Se as disciplinas mudaram, sincronizamos as associações
        if disciplina_nomes is not None:
            # DELETE: Remove todas as associações antigas do professor
            supabase.table('professordisciplina').delete().eq('id_professor', str(professor_uuid)).execute()
            
            # SELECT & INSERT: Busca as disciplinas pelo nome e cria as novas associações
            if disciplina_nomes and len(disciplina_nomes) > 0:
                disciplinas_ids_response = supabase.table("disciplina").select("id_disciplina", "nome_disciplina").in_("nome_disciplina", disciplina_nomes).execute()
                disciplinas_encontradas = disciplinas_ids_response.data
                
                if len(disciplinas_encontradas) > 0:
                    associations_to_create = [
                        {"id_professor": str(professor_uuid), "id_disciplina": disciplina['id_disciplina']}
                        for disciplina in disciplinas_encontradas
                    ]
                    supabase.table("professordisciplina").insert(associations_to_create).execute()
        
        # Buscar professor atualizado para retornar
        prof_response = supabase.table("professor").select("*").eq('id', professor_uuid).single().execute()
        
        prof = prof_response.data
        prof_id = str(prof.get('id', ''))
        
        # Busca disciplinas associadas diretamente da tabela professordisciplina
        pd_response = supabase.table("professordisciplina").select(
            """
            disciplina!inner(id_disciplina, nome_disciplina)
            """
        ).eq('id_professor', prof_id).execute()
        
        # Processar as disciplinas associadas ao professor
        disciplina_nomes_final = []
        if pd_response.data:
            for pd in pd_response.data:
                disciplina_info = pd.get('disciplina')
                if disciplina_info and isinstance(disciplina_info, dict):
                    nome = disciplina_info.get('nome_disciplina', '')
                    if nome and nome not in disciplina_nomes_final:
                        disciplina_nomes_final.append(nome)
        
        prof['disciplina_nomes'] = disciplina_nomes_final
        
        return Professor.model_validate(prof)
    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

### ENDPOINT PARA DELETAR UM PROFESSOR ###
@router.delete("/delete/{id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_professor(id: str, current_user: dict = Depends(require_admin_or_coordenador_or_professor)):
    # ** Lembrar que essa função remove o usuário do sistema de autenticação do Supabase.
    try:
        # Verificar se o id é um UUID (tem hífens e formato UUID) ou id_funcional
        uuid_pattern = r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
        is_uuid = bool(re.match(uuid_pattern, id, re.IGNORECASE))
        
        # Executa o select no Supabase | tabela = professor | identificado do professor = id ou id_funcional
        if is_uuid:
            # Se for UUID, busca diretamente pelo id
            response = supabase.table("professor").select("id").eq("id", id).execute()
        else:
            # Se não for UUID, busca pelo id_funcional
            response = supabase.table("professor").select("id").eq("id_funcional", id).execute()

        # Verifica se algum dado foi retornado (o que significa que algo foi encontrado)
        if not response.data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Professor não encontrado para deletar.")

        professor_id = response.data[0]['id']

        # Executa o delete no Supabase | tabela = professor | identificado do professor = id
        delete_response = supabase.table('professor').delete().eq('id', professor_id).execute()

        if not delete_response.data:
            raise HTTPException(status_code=500, detail="Falha ao deletar o perfil do professor. A operação foi abortada.")

        # Deletar o usuário do Auth usando API REST
        auth_delete_response = supabase.auth.admin.delete_user(professor_id)
        try:
            delete_url = f"{settings.SUPABASE_URL}/auth/v1/admin/users/{professor_id}"
            headers = {
                "apikey": settings.SUPABASE_SERVICE_KEY,
                "Authorization": f"Bearer {settings.SUPABASE_SERVICE_KEY}",
                "Content-Type": "application/json"
            }
            requests.delete(delete_url, headers=headers)
        except Exception as auth_exc:
            print(f"AVISO: Falha ao deletar usuário do Auth: {auth_exc}")
            # Não levanta exceção aqui para não abortar a operação
        
        # HTTP 204 não deve retornar nenhum corpo de resposta
        return

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))




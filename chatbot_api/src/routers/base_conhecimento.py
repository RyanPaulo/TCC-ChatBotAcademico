from datetime import datetime
# from idlelib.query import Query
from typing import Annotated
from fastapi import APIRouter, HTTPException, status, Query, Depends
from ..supabase_client import supabase
from ..schemas.sch_base_conhecimento import BaseConhecimento, BaseConhecimentoCreate, BaseConhecimentoUpdate, DocumentoURLResponse
from ..dependencies import require_admin_or_coordenador_or_professor, require_all, require_admin_or_coordenador
import uuid
import json

# --- ROUTER BASE DE CONHECIMENTO PARA O RASA AI ---

router = APIRouter(
    prefix="/baseconhecimento",
    tags=["Base de Conhecimento"]
)

# Função para simplificar a converção das respostas do banco de volta para o formato do schema
def convert_json_fields(db_data: dict) -> dict:
    # Converte campos JSONB de string para lista em um dicionário.
    if isinstance(db_data.get('palavra_chave'), str):
        db_data['palavra_chave'] = json.loads(db_data['palavra_chave'])
    if isinstance(db_data.get('visivel_para'), str):
        db_data['visivel_para'] = json.loads(db_data['visivel_para'])
    return db_data

### ENDPOINT PARA CADASTRAR CONHECIMENTO ###
@router.post("/", status_code=status.HTTP_201_CREATED, response_model=BaseConhecimento)
def create_conhecimento(item: BaseConhecimentoCreate, current_user: dict = Depends(require_admin_or_coordenador_or_professor)):
    try:
        payload = item.model_dump()

        if 'palavra_chave' in payload:
            payload['palavra_chave'] = json.dumps(payload['palavra_chave'])
        if 'visivel_para' in payload:
            payload['visivel_para'] = json.dumps(payload['visivel_para'])

        # Convertendo os id em strings para que garata compartibilidade
        if payload.get('id_disciplina'):
            payload['id_disciplina'] = str(payload['id_disciplina'])
        
        if payload.get('id_tcc'):
            payload['id_tcc'] = str(payload['id_tcc'])

        if payload.get('id_aps'):
            payload['id_aps'] = str(payload['id_aps'])

        if payload.get('id_estagio'):
            payload['id_estagio'] = str(payload['id_estagio'])

        if payload.get('id_hora_complementares'):
            payload['id_hora_complementares'] = str(payload['id_hora_complementares'])

        response = supabase.table("baseconhecimento").insert(payload).execute()

        # Filtro de erro, para um mensagem mais clara
        if not response.data:
            error_detail = "Erro ao inserir na base de conhecimento"

            try:
                api_error = response.model_dump()
                if api_error and 'message' in api_error:
                    error_detail = api_error['message']
            except Exception:
                pass

            raise HTTPException(status_code=500, detail=error_detail)


        db_data = response.data[0]

        return convert_json_fields(db_data)

    except Exception as e:
        # Tratamento de erro para chave estrangeira (se o disciplina não existir)
        if "violates foreign key constraint" in str(e).lower() and "fk_disciplina" in str(e).lower():
            raise HTTPException(status_code=404, detail=f"A disciplina com ID '{item.id_disciplina}' não foi encotrada.")
        raise HTTPException(status_code=400, detail=str(e))

### ENDPOINT PARA LISTA TODOS OS ITEM DE CONHECIMENTO ###
@router.get("/get_buscar")
async def buscar_conhecimento(q: Annotated[str, Query(..., min_length=3, description="Termo de busca para a pergunta do usuário")], current_user: dict = Depends(require_all)):
    try:
        response = supabase.rpc("buscar_conteudo", {"query": q}).execute()


        if not response.data:
            raise HTTPException(status_code=404, detail="Nenhum conteúdo relevante encontrado.")

        # Retorna apenas uma lista de textos (resumos)
        return {"contextos": [item['conteudo_processado'] for item in response.data]}
    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        print(f"ERRO DETALHADO NA BUSCA: {e}")
        raise HTTPException(status_code=500, detail=f"Erro ao buscar no banco de dados: {e}")

### ENDPOINT PARA CONSULTA UM ITEM DE CONHECIMENTO ###
@router.get("/get_baseconhecimento_id/{item_id}", response_model=BaseConhecimento)
def get_conhecimento(item_id: uuid.UUID, current_user: dict = Depends(require_all)):
    try:
        response = supabase.table("baseconhecimento").select("*").eq('id_conhecimento', str(item_id)).single().execute()

        if not response.data:
            raise HTTPException(status_code=404, detail="Item de conhecimento não encontrado.")

        db_data = response.data
        return convert_json_fields(db_data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

### ENDPOINT PARA CONSULTA URL DO DOCUMENTO POR TERMO DE BUSCA ###
@router.get("/get_baseconhecimento_url_documento/{termo_busca}", response_model=DocumentoURLResponse)
def get_url_documento_por_termo(termo_busca: str, current_user: dict = Depends(require_all)):
    """
    Busca o URL do documento na base de conhecimento por termo.
    Faz busca flexível no nome do arquivo e nas palavras-chave.
    Exemplo: "cocomo" encontrará "CoCoMo_Marcelo.pdf"
    """
    try:
        # Remove espaços e converte para minúsculas para busca mais flexível
        termo_limpo = termo_busca.strip().lower()
        
        # Busca por nome do arquivo (busca parcial case-insensitive)
        response_nome = supabase.table("baseconhecimento").select(
            "url_documento, nome_arquivo_origem"
        ).ilike('nome_arquivo_origem', f'%{termo_limpo}%').execute()
        
        # Se não encontrou por nome, tenta buscar nas palavras-chave
        if not response_nome.data:
            # Busca em todos os registros e filtra por palavra-chave no código
            response_todos = supabase.table("baseconhecimento").select(
                "url_documento, nome_arquivo_origem, palavra_chave"
            ).execute()
            
            # Filtra registros onde o termo está nas palavras-chave
            resultados = []
            for item in response_todos.data:
                palavras_chave = item.get('palavra_chave', [])
                # Se palavra_chave é string JSON, converte
                if isinstance(palavras_chave, str):
                    try:
                        palavras_chave = json.loads(palavras_chave)
                    except:
                        palavras_chave = []
                
                # Verifica se o termo está em alguma palavra-chave
                if any(termo_limpo in str(palavra).lower() for palavra in palavras_chave):
                    resultados.append({
                        'url_documento': item.get('url_documento'),
                        'nome_arquivo_origem': item.get('nome_arquivo_origem')
                    })
            
            if resultados:
                # Retorna o primeiro resultado encontrado
                resultado = resultados[0]
                if not resultado.get('url_documento'):
                    raise HTTPException(status_code=404, detail="Documento encontrado mas sem URL disponível.")
                return resultado
        else:
            # Encontrou por nome do arquivo
            resultado = response_nome.data[0]
            if not resultado.get('url_documento'):
                raise HTTPException(status_code=404, detail="Documento encontrado mas sem URL disponível.")
            return resultado
        
        # Se chegou aqui, não encontrou nada
        raise HTTPException(
            status_code=404, 
            detail=f"Nenhum documento encontrado com o termo '{termo_busca}'. Tente buscar por parte do nome do arquivo ou palavra-chave."
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao buscar documento: {str(e)}")


### ENDPOINT PARA LISTAR TODOS OS ITENS DE CONHECIMENTO ###
@router.get("/get_lista_conhecimento", response_model=list[BaseConhecimento])
def list_all_conhecimento(current_user: dict = Depends(require_all)):

    try:
        response = supabase.table("baseconhecimento").select("*").execute()
        
        if not response.data:
            return []
        
        # Converte cada item
        return [convert_json_fields(item) for item in response.data]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao listar base de conhecimento: {e}")


### ENDPOINT PARA ATUALIZAR UM ITEM DE CONHECIMENTO ###
@router.put("/update/{item_id}", response_model=BaseConhecimento)
def update_conhecimento(item_id: uuid.UUID, item: BaseConhecimentoUpdate, current_user: dict = Depends(require_admin_or_coordenador)):
    try:
        payload = item.model_dump(exclude_unset=True)

        if not payload:
            raise HTTPException(status_code=400, detail="Nenhum dado fornecido para atualização.")

        if payload.get('id_disciplina'):
            payload['id_disciplina'] = str(payload['id_disciplina'])

        if payload.get('id_tcc'):
            payload['id_tcc'] = str(payload['id_tcc'])

        if payload.get('id_aps'):
            payload['id_aps'] = str(payload['id_aps'])

        if payload.get('id_estagio'):
            payload['id_estagio'] = str(payload['id_estagio'])
            
        if payload.get('id_hora_complementares'):
            payload['id_hora_complementares'] = str(payload['id_hora_complementares'])

        payload['atualizado_em'] = datetime.now().isoformat()

        response = supabase.table("baseconhecimento").update(payload).eq('id_conhecimento', str(item_id)).execute()

        if not response.data:
            raise HTTPException(status_code=404, detail=f"item com ID '{item_id}' não encontrado.")


        db_data = response.data[0]

        return convert_json_fields(db_data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

### ENDPOINT PARA DELETAR UM ITEM DE CONHECIMENTO ###
@router.delete("/delete/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_conhecimento(item_id: uuid.UUID, current_user: dict = Depends(require_admin_or_coordenador_or_professor)):
    try:
        response = supabase.table("baseconhecimento").delete().eq('id_conhecimento', str(item_id)).execute()

        if not response.data:
            raise HTTPException(status_code=404, detail=f"Item com ID '{item_id}' não encontrado.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
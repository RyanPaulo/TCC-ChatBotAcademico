
from typing import List, Optional
from datetime import date, time
from fastapi import APIRouter, HTTPException, status, Depends
from ..supabase_client import supabase
from ..schemas.sch_avaliacao import AvaliacaoCreate, Avaliacao, AvaliacaoUpdate, TipoAvaliacaoEnum
from ..dependencies import get_current_user, require_admin_or_coordenador_or_professor, require_all, require_admin, require_admin_or_coordenador
import uuid

# --- ROUTER AVALIACAO ---

router = APIRouter(
    prefix="/avaliacao",
    tags=["Avaliação"]  
)


### ENDPOINT PARA CADASTRAR AVALIACAO ###
@router.post("/", status_code=status.HTTP_201_CREATED, response_model=Avaliacao)
def create_avaliacao(avaliacao_data: AvaliacaoCreate, current_user: dict = Depends(require_admin_or_coordenador_or_professor)):
    try:
        # Converte os dados do Pydantic para um dicionário
        payload = avaliacao_data.model_dump()

        # Converte campos de data/hora/uuid para string, se existirem
        for key, value in payload.items():
            if isinstance(value, (date, time, uuid.UUID)):
                payload[key] = str(value)
        
        response = supabase.table("avaliacao").insert(payload).execute()

        if not response.data:
            raise HTTPException(status_code=500, detail="Erro ao criar a avaliação.")

        return response.data[0]

    except Exception as e:
        if "violates foreign key constraint" in str(e).lower():
            raise HTTPException(status_code=404, detail="A disciplina ou o aplicador especificado não foi encontrado.")
        raise HTTPException(status_code=400, detail=str(e))

### ENDPOINT PARA CONSULTAR AS AVALIAÇÃO USANDO O ID ###
@router.get("/get_avaliacao/{avalicao_id}", response_model=Avaliacao)
def get_avaliacao(avaliacao_id: uuid.UUID, current_user: dict = Depends(require_all)):
    try:
        response = supabase.table("avaliacao").select("*").eq('id_avaliacao', str(avaliacao_id)).single().execute()

        if not response.data:
            raise HTTPException(status_code=404, detail="Avaliação não encontrada.")

        return response.data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

### ENDPOINT PARA CONSULTAR AS AVALIAÇÕES POR DISCIPLINA ###
@router.get("/disciplina/{disciplina_id}", response_model=List[Avaliacao])
def get_avaliacoes_por_disciplina(disciplina_id: uuid.UUID, current_user: dict = Depends(require_all)):
    try:
        disciplina_id_str = str(disciplina_id)
        print(f"[DEBUG] Buscando avaliações para disciplina_id: {disciplina_id_str}")
        response = supabase.table("avaliacao").select("*").eq("id_disciplina", disciplina_id_str).execute()
        
        print(f"[DEBUG] Total de avaliações encontradas: {len(response.data) if response.data else 0}")
        if response.data and len(response.data) > 0:
            print(f"[DEBUG] Primeira avaliação: {response.data[0]}")
        
        # Retorna a lista de dados (pode ser uma lista vazia, o que é um resultado válido)
        return response.data
    except Exception as e:
        print(f"[ERROR] Erro ao buscar avaliações por disciplina: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

### ENDPOINT PARA ATUALIZAR UMA AVALIAÇÃO POR TIPO E DISCIPLINA ###
@router.put("/disciplina/{disciplina_id}/tipo/{tipo_avaliacao}", response_model=Avaliacao)
def update_avaliacao_por_tipo_e_disciplina(
    disciplina_id: uuid.UUID, 
    tipo_avaliacao: str, # Recebemos como string simples da URL
    avaliacao_data: AvaliacaoUpdate,
    current_user: dict = Depends(require_admin_or_coordenador)
):
    try:
        # Pega apenas os campos que foram enviados na requisição
        payload = avaliacao_data.model_dump(exclude_unset=True)

        if not payload:
            raise HTTPException(status_code=400, detail="Nenhum dado fornecido para atualização.")

        # Converte campos de data/hora/uuid para string, se existirem
        for key, value in payload.items():
            if isinstance(value, (date, time, uuid.UUID)):
                payload[key] = str(value)

        # Valida se o tipo_avaliacao é válido
        try:
            tipo_validado = tipo_avaliacao.upper()
            TipoAvaliacaoEnum(tipo_validado)  # Valida contra o Enum
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Tipo de avaliação inválido. Valores aceitos: {', '.join([e.value for e in TipoAvaliacaoEnum])}"
            )

        # A "mágica" está aqui: encadeamos dois .eq() para criar um "WHERE ... AND ..."
        response = supabase.table("avaliacao").update(payload).eq(
            "id_disciplina", str(disciplina_id)
        ).eq(
            "tipo_avaliacao", tipo_avaliacao.upper() # Usamos .upper() para garantir consistência (ex: 'np1' vira 'NP1')
        ).execute()

        if not response.data:
            raise HTTPException(
                status_code=404, 
                detail=f"Nenhuma avaliação do tipo '{tipo_avaliacao.upper()}' encontrada para a disciplina especificada."
            )

        # O Supabase retorna uma lista de registros atualizados, pegamos o primeiro.
        return response.data[0]
        
    except Exception as e:
        # Re-lança a exceção se já for uma HTTPException
        if isinstance(e, HTTPException):
            raise e
        # Captura outros erros genéricos
        raise HTTPException(status_code=500, detail=str(e))

### ENDPOINT PARA DELETAR UMA AVALIAÇÃO ###
@router.delete("/{avaliacao_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_avaliacao(
    avaliacao_id: uuid.UUID,
    current_user: dict = Depends(require_admin_or_coordenador_or_professor)
):
    """
    Deleta uma avaliação específica.
    """
    try:
        response = supabase.table("avaliacao").delete().eq("id_avaliacao", str(avaliacao_id)).execute()

        if not response.data:
            raise HTTPException(status_code=404, detail="Avaliação não encontrada.")

        return None  # Retorna None para status 204
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


from typing import List
from fastapi import APIRouter, HTTPException, status, Depends
from ..supabase_client import supabase
from ..schemas.sch_cronograma import CronogramaCreate, Cronograma, CronogramaUpdate
from ..dependencies import require_admin_or_coordenador_or_professor, require_all
import uuid

# --- ROUTER CRONOGRAMA ---

router = APIRouter(
    prefix="/cronograma",
    tags=["cronograma"]
)


### ENDPOINT PARA REGISTRAR CRONOGRAMA ###
@router.post("/", status_code=status.HTTP_201_CREATED, response_model=Cronograma)
def create_cronograma(cronograma_data: CronogramaCreate, current_user: dict = Depends(require_admin_or_coordenador_or_professor)):
    try:
        cronograma_payload = cronograma_data.model_dump()

        # Converter as datas para o padrao json
        if cronograma_payload.get('data_inicio_semestre'):
            cronograma_payload['data_inicio_semestre'] = cronograma_payload['data_inicio_semestre'].isoformat()

        if cronograma_payload.get('data_fim_semestre'):
            cronograma_payload['data_fim_semestre'] = cronograma_payload['data_fim_semestre'].isoformat()


        cronograma_payload['hora_inicio'] = cronograma_payload['hora_inicio'].isoformat()
        cronograma_payload['hora_fim'] = cronograma_payload['hora_fim'].isoformat()

        # Convertendo os id em strings para que garata compartibilidade
        cronograma_payload['id_disciplina'] = str(cronograma_payload['id_disciplina'])


        db_response = supabase.table("cronograma").insert(cronograma_payload).execute()

        if not db_response.data:
            raise HTTPException(status_code=500, detail="Erro ao cadatrar a cronograma")

        return db_response.data[0]
    except Exception as e:
        if "violates foreign key constraint" in str(e).lower():
            detail = "A disciplina associado não foi encontrado."
            raise HTTPException(status_code=404, detail=detail)
        raise HTTPException(status_code=400, detail=str(e))

#### ENDPOINT PARA CONSULTAR OS CRONOGRAMA USANDO O ID ####
@router.get("/get_cronograma_id/{cronograma_id}", response_model=Cronograma)
def get_cronograma(cronograma_id: uuid.UUID, current_user: dict = Depends(require_all)):
    try:
        db_response = supabase.table("cronograma").select("*").eq('id_cronograma', str(cronograma_id)).single().execute()

        if not db_response.data:
            raise HTTPException(status_code=404, detail="Cronograma não encotrada.")

        return db_response.data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

### ENDPOINT PARA CONSULTAR O CRONOGRAMA VIA O ID DA DISCIPLINA ###
@router.get("/disciplina/{disciplina_id}", response_model=List[Cronograma])
def get_cronogramas_por_disciplina(disciplina_id: uuid.UUID, current_user: dict = Depends(require_all)):
    try:
        # Consulta a tabela 'cronograma' e filtra pela coluna 'id_disciplina'
        db_response = supabase.table("cronograma").select(
            "*"
        ).eq(
            'id_disciplina', str(disciplina_id)
        ).execute()

        return db_response.data

    except Exception as e:
        # Captura erros inesperados do banco de dados ou de conexão
        raise HTTPException(status_code=500, detail=f"Um erro inesperado ocorreu: {str(e)}")


##### ENDPOINT PARA ATUALIZAR O CRONOGRAMA USANDO O ID ####
@router.put("/updade/{cronograma_id}", response_model=Cronograma)
def update_cronograma(cronograma_id: uuid.UUID, cronograma_data: CronogramaUpdate, current_user: dict = Depends(require_admin_or_coordenador_or_professor)):
    try:
        update_payload = cronograma_data.model_dump(exclude_unset=True)

        # ifs para converster data e hora para o padrao json
        if 'data_inicio_semestre' in update_payload:
            update_payload['data_inicio_semestre'] = update_payload['data_inicio_semestre'].isoformat()

        if 'data_fim_semestre' in update_payload:
            update_payload['data_fim_semestre'] = update_payload['data_fim_semestre'].isoformat()

        if 'hora_inicio' in update_payload:
            update_payload['hora_inicio'] = update_payload['hora_inicio'].isoformat()

        if 'hora_fim' in update_payload:
            update_payload['hora_fim'] = update_payload['hora_fim'].isoformat()

        if 'id_disciplina' in update_payload:
            update_payload['id_disciplina'] = update_payload['id_disciplina'].isoformat()

        # Para filtro de erros
        if not update_payload:
            raise HTTPException(status_code=400, detail="Nenhum dado fornecido para atualização.")

        db_response = supabase.table('cronograma').update(update_payload).eq('id_cronograma', str(cronograma_id)).execute()

        if not db_response.data:
            raise HTTPException(status_code=404, detail="Cronograma não encontrada para atualização.")

        return db_response.data[0]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

##### ENDPOINT PARA DELETAR UM CRONOGRAMA USANDO O ID ####
@router.delete("/delete/{cronograma_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_cronograma(cronograma_id: uuid.UUID, current_user: dict = Depends(require_admin_or_coordenador_or_professor)):
    try:

        db_response = supabase.table('cronograma').delete().eq('id_cronograma', str(cronograma_id)).execute()

        if not db_response.data:
            raise HTTPException(status_code=404, detail="Cronograma não encontrado para deletar")

        return
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

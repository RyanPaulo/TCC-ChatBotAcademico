from typing import List
from fastapi import APIRouter, HTTPException, status, Depends
from ..supabase_client import supabase
from ..schemas.sch_aviso import Aviso, AvisoCreate, AvisoUpdate
from ..dependencies import require_admin_or_coordenador, require_all, require_admin_or_coordenador_or_professor
import uuid

# --- ROUTER AVISO ---

router = APIRouter(
    prefix="/aviso",
    tags=["Aviso"]
)

### ENDPOINT PARA REGISTRAR AVISO ###
@router.post("/", status_code=status.HTTP_201_CREATED, response_model=Aviso)
def create_aviso(aviso_data: AvisoCreate, current_user: dict = Depends(require_admin_or_coordenador)):
    try:
        aviso_payload = aviso_data.model_dump(exclude_unset=True)

        aviso_payload['data'] = aviso_payload['data'].isoformat()

        if 'id_disciplina' in aviso_payload and aviso_payload['id_disciplina'] is not None:
            aviso_payload['id_disciplina'] = str(aviso_payload['id_disciplina'])

        if 'id_professor' in aviso_payload and aviso_payload['id_professor'] is not None:
            aviso_payload['id_professor'] = str(aviso_payload['id_professor'])

        if 'id_coordenador' in aviso_payload and aviso_payload['id_coordenador'] is not None:
            aviso_payload['id_coordenador'] = str(aviso_payload['id_coordenador'])

        response = supabase.table("aviso").insert(aviso_payload).execute()

        if not response.data:
            raise HTTPException(status_code=500, detail="Erro ao registrar o aviso")

        return response.data[0]

    except Exception as e:
        if "violates foreign key constraint" in str(e).lower():
            if'fk_aviso_professor' in str(e).lower():
                raise HTTPException(status_code=404, detail=f"O professor com ID '{aviso_data.id_professor}' não foi encontrado.")
            if 'fk_aviso_coordenador' in str(e).lower():
                raise HTTPException(status_code=404, detail=f"O coordenador com ID '{aviso_data.id_coordenador}' não foi encontrado.")
        raise HTTPException(status_code=400, detail=str(e))

### ENDPOINT PARA CONSULTA DA TABELA AVISO ###
@router.get("/get_aviso_id/{aviso_id}", response_model=Aviso)
def get_aviso(aviso_id: uuid.UUID, current_user: dict = Depends(require_all)):
    try:
        response = supabase.table("aviso").select("*").eq('id_aviso', str(aviso_id)).sigle().execute()

        if not response.data:
            raise HTTPException(status_code=404, detail="Aviso não encotrada.")

        return  response.data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

### ENDPOINT PARA LISTAR TODOS OS AVISOS ###
@router.get("/get_lista_aviso/", response_model=List[Aviso])
def get_all_avisos(current_user: dict = Depends(require_all)):
    try:
        response = supabase.table("aviso").select("*").execute()
        return response.data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

### ENDPOINT PARA ATUALIZAR UM AVISO ###
@router.put("/update/{aviso_id}", response_model=Aviso)
def update_aviso(aviso_id: uuid.UUID, aviso_data: AvisoUpdate, current_user: dict = Depends(require_admin_or_coordenador)):
    try:
        update_payload = aviso_data.model_dump(exclude_unset=True)

        update_payload['data'] = update_payload['data'].isoformat()


        if 'id_professor' in update_payload and update_payload['id_professor'] is not None:
            update_payload['id_professor'] = str(update_payload['id_professor'])

        if 'id_coordenador' in update_payload and update_payload['id_coordenador'] is not None:
            update_payload['id_coordenador'] = str(update_payload['id_coordenador'])

        response = supabase.table('aviso').update(update_payload).eq('id_aviso', str(aviso_id)).execute()

        if not response.data:
            raise HTTPException(status_code=404, detail="Aviso não encontrada para atualização.")

        return response.data[0]
    except Exception as e:
        if "violates foreign key constraint" in str(e).lower() and "fk_professor" in str(e).lower():
            raise  HTTPException(status_code=404, detail=f"O id do professor nao foi reconhecido {aviso_data.id_professor}")

        raise HTTPException(status_code=500, detail=str(e))

### ENDPOIND PARA DELETAR O AVISO ###
@router.delete("/delete/{aviso_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_aviso(aviso_id: uuid.UUID, current_user: dict = Depends(require_admin_or_coordenador_or_professor)):
    try:
        response = supabase.table('aviso').delete().eq('id_aviso', str(aviso_id)).execute()

        if not response.data:
            raise HTTPException(status_code=404, detail="O aviso não foi encotrado para deletar.")

        return
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
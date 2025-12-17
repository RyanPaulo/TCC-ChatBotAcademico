from fastapi import APIRouter, HTTPException, status, Depends
from datetime import timedelta
from ..supabase_client import supabase
from ..schemas.sch_curso import Curso, CursoCreate, CursoUpadate
from ..dependencies import require_admin_or_coordenador_or_professor, require_all, require_admin_or_coordenador
import uuid
import json
import re

router = APIRouter(
    prefix="/curso",
    tags=["Curso"]
)

def convert_json_fields(db_data: dict) -> dict:
    if isinstance(db_data.get('modalidade'), str):
        db_data['modalidade'] = json.loads(db_data['modalidade'])
    
    if 'carga_horaria' in db_data and db_data['carga_horaria'] is not None:
        carga_horaria = db_data['carga_horaria']
        
        if isinstance(carga_horaria, str):
            carga_horaria_str = carga_horaria.strip()
            
            if carga_horaria_str.startswith('P'):
                try:
                    days_match = re.search(r'(\d+)D', carga_horaria_str)
                    hours_match = re.search(r'(\d+)H', carga_horaria_str)
                    minutes_match = re.search(r'(\d+)M', carga_horaria_str)
                    
                    days = int(days_match.group(1)) if days_match else 0
                    hours = int(hours_match.group(1)) if hours_match else 0
                    minutes = int(minutes_match.group(1)) if minutes_match else 0
                    
                    total_hours = (days * 24) + hours + (minutes / 60)
                    db_data['carga_horaria'] = int(total_hours)
                except (ValueError, AttributeError):
                    pass
            
            elif ':' in carga_horaria_str:
                try:
                    horas_str = carga_horaria_str.split(':')[0]
                    db_data['carga_horaria'] = int(horas_str)
                except (ValueError, IndexError):
                    pass
            else:
                try:
                    db_data['carga_horaria'] = int(carga_horaria_str)
                except ValueError:
                    pass
        
        elif isinstance(carga_horaria, timedelta):
            total_seconds = int(carga_horaria.total_seconds())
            total_hours = total_seconds // 3600
            db_data['carga_horaria'] = total_hours
        
        elif isinstance(carga_horaria, int):
            db_data['carga_horaria'] = carga_horaria

    return db_data


@router.post("/", status_code=status.HTTP_201_CREATED, response_model=Curso)
def create_curso(item: CursoCreate, current_user: dict = Depends(require_admin_or_coordenador_or_professor)):
    try:
        create_payload = item.model_dump(mode='python')

        if 'carga_horaria' in create_payload:
            if isinstance(create_payload['carga_horaria'], timedelta):
                total_seconds = int(create_payload['carga_horaria'].total_seconds())
                horas = total_seconds // 3600
                create_payload['carga_horaria'] = f"{horas} hours"

        if 'modalidade' in create_payload:
            if create_payload['modalidade']:
                create_payload['modalidade'] = json.dumps(create_payload['modalidade'])
            else:
                create_payload['modalidade'] = '[]'

        db_response = supabase.table("curso").insert(create_payload).execute()

        if not db_response.data:
            raise HTTPException(status_code=500, detail="Erro ao cadastrar o Curso.")

        db_data = db_response.data[0]
        return convert_json_fields(db_data)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/get_curso/{curso_id}", response_model=Curso)
def get_curso(curso_id: uuid.UUID, current_user: dict = Depends(require_all)):
    try:
        db_response = supabase.table("curso").select("*").eq('id_curso', str(curso_id)).single().execute()

        if not db_response.data:
            raise HTTPException(status_code=404, detail="Curso não encontrado.")

        db_data = db_response.data
        return convert_json_fields(db_data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/get_curso_nome/{nome_curso}", response_model=Curso)
def get_curso_nome(nome_curso: str, current_user: dict = Depends(require_all)):
    try:
        db_response = supabase.table("curso").select("*").eq('nome_curso', nome_curso).single().execute()

        if not db_response.data:
            raise HTTPException(status_code=404, detail=f"Curso com nome '{nome_curso}' não encontrado.")

        db_data = db_response.data
        return convert_json_fields(db_data)
    except Exception as e:
        if "JSON object requested, multiple (or no) rows returned" in str(e):
            raise HTTPException(status_code=404, detail=f"Curso com nome '{nome_curso}' não encontrado ou múltiplos cursos encontrados.")
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/update/{curso_id}", response_model=Curso)
def update_curso(curso_id: uuid.UUID, curso_data: CursoUpadate, current_user: dict = Depends(require_admin_or_coordenador)):
    try:
        update_payload = curso_data.model_dump(exclude_unset=True)

        if 'modalidade' in update_payload:
            update_payload['modalidade'] = json.dumps(update_payload['modalidade'])

        if 'carga_horaria' in update_payload and isinstance(update_payload['carga_horaria'], timedelta):
            total_seconds = int(update_payload['carga_horaria'].total_seconds())
            horas = total_seconds // 3600
            update_payload['carga_horaria'] = f"{horas} hours"

        db_response = supabase.table('curso').update(update_payload).eq('id_curso', str(curso_id)).execute()

        if not db_response.data:
            raise HTTPException(status_code=404, detail=f"Curso com o ID '{curso_id}' não encontrado para atualização.")

        db_data = db_response.data[0]
        return convert_json_fields(db_data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/detele/{curso_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_curso(curso_id: uuid.UUID, current_user: dict = Depends(require_admin_or_coordenador_or_professor)):
    try:
        db_response = supabase.table('curso').delete().eq('id_curso', str(curso_id)).execute()

        if not db_response.data:
            raise HTTPException(status_code=404, detail="Curso não encotrado para deletar.")

        return
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))





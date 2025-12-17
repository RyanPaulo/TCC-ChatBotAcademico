from typing import List
from ..schemas.sch_cronograma import Cronograma
from fastapi import APIRouter, HTTPException, status, Depends
from ..supabase_client import supabase
from ..schemas.sch_disciplina import DisciplinaCreate, Disciplina, DisciplinaUpdate, DisciplinaEmenta
from ..dependencies import require_admin_or_coordenador_or_professor, require_all, require_admin_or_coordenador
import uuid

# --- ROUTER DISCIPLINA ---

router = APIRouter(
    prefix="/disciplinas",
    tags=["Disciplina"]
)

### ENDPOINT PARA CADASTRAR DISCIPLINAS #####
@router.post("/", status_code=status.HTTP_201_CREATED, response_model=Disciplina)
def create_disciplina(disciplina_data: DisciplinaCreate, current_user: dict = Depends(require_admin_or_coordenador_or_professor)):
    try:
        disciplina_payload = disciplina_data.model_dump()
        
        # Insere a disciplina na tabela disciplina
        db_response = supabase.table("disciplina").insert(disciplina_payload).execute()

        if not db_response.data:
            raise HTTPException(status_code=500, detail="Erro ao cadastrar a disciplina")

        return db_response.data[0]

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

##### ENDPOINT PARA CONSULTAR AS DISCIPLINAS USANDO O ID ####
@router.get("/get_diciplina_id/{disciplina_id}", response_model=Disciplina)
def get_disciplina_detalhado(disciplina_id: uuid.UUID, current_user: dict = Depends(require_all)):
    try:
        db_response = supabase.table("disciplina").select(
            """
            *,
            professordisciplina!left(
                professor!inner(nome_professor, sobrenome_professor)
            ),
            cronograma!left(tipo_aula)
            """
        ).eq(
            'id_disciplina', str(disciplina_id)
        ).single().execute()

        if not db_response.data:
            raise HTTPException(status_code=404, detail="Disciplina não encontrada.")


        data = db_response.data

        # 1. Processar os professores
        professores_list = []
        # A resposta pode não conter a chave se não houver relação
        if data.get('professordisciplina'):
            for item in data['professordisciplina']:
                if item and item.get('professor'):  # Checagem dupla de segurança
                    professores_list.append(item['professor'])
        data['professores'] = professores_list
        if 'professordisciplina' in data:
            del data['professordisciplina']

        # 2. Processar o tipo de aula
        # A resposta pode não conter a chave se não houver relação
        if data.get('cronograma') and data['cronograma']:
            data['tipo_aula'] = data['cronograma'][0]['tipo_aula']
        else:
            data['tipo_aula'] = None
        if 'cronograma' in data:
            del data['cronograma']


        return Disciplina.model_validate(data)

        # return db_response.data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

### ENDPOINT PARA RETORNAR O CONTEUDO DA EMENTA ###
@router.get("/get_ementa/{nome_disciplina}", response_model=DisciplinaEmenta)
def get_ementa_da_disciplina(nome_disciplina: str, current_user: dict = Depends(require_all)):
    try:
        # seleciona apenas a coluna 'ementa' da tabela 'Disciplina' usando o nome
        db_response = supabase.table("disciplina").select(
            "ementa"
        ).ilike(
            'nome_disciplina', f"%{nome_disciplina}%"
        ).single().execute()


        if not db_response.data:
            raise HTTPException(status_code=404, detail=f"Disciplina '{nome_disciplina}' não encontrada.")

        return db_response.data

    except Exception as e:
        if "JSON object requested, multiple (or no) rows returned" in str(e):
             raise HTTPException(status_code=404, detail=f"Disciplina '{nome_disciplina}' não encontrada.")
        raise HTTPException(status_code=500, detail=str(e))

#### ENDPOINT PARA BUSCAR O CRONOGRAMA DE UMA DISCIPLINA PELO NOME ####
@router.get("/get_diciplina_nome/{nome_disciplina}/cronograma", response_model=List[Cronograma]) #tags=["disciplina"]
def get_cronograma_por_disciplina(nome_disciplina: str, current_user: dict = Depends(require_all)):
    try:
        disciplina_response = supabase.table("disciplina").select("id_disciplina").ilike("nome_disciplina", f"%{nome_disciplina}%").execute()

        if not disciplina_response.data:
            raise HTTPException(status_code=404, detail=f"Disciplina '{nome_disciplina}' não encontrada.")

        disciplina_id = disciplina_response.data[0]['id_disciplina']

        cronograma_response = supabase.table("cronograma").select("*").eq('id_disciplina', disciplina_id).execute()

        if not cronograma_response.data:
            raise HTTPException(status_code=404, detail=f"Nenhum cronograma encontrado para a disciplina '{nome_disciplina}'.")

        return cronograma_response.data


    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        # Captura outras exceções genéricas
        raise HTTPException(status_code=500, detail=str(e ))

### ENDPOINT PARA LISTAR TODOS OS DISCIPLINA CADASTRADOS NO BD ###
@router.get("/lista_disciplina/", response_model=list[Disciplina])
def get_all_disciplina(current_user: dict = Depends(require_all)):
    try:
        # Busca disciplinas com join para professores
        db_response = supabase.table("disciplina").select(
            """
            *,
            professordisciplina!left(
                professor!inner(nome_professor, sobrenome_professor)
            )
            """
        ).execute()
        
        # Processa cada disciplina para formatar os professores
        disciplinas_formatadas = []
        for disc in db_response.data:
            # Processar os professores
            professores_list = []
            if disc.get('professordisciplina'):
                for item in disc['professordisciplina']:
                    if item and item.get('professor'):
                        professores_list.append(item['professor'])
            disc['professores'] = professores_list
            if 'professordisciplina' in disc:
                del disc['professordisciplina']
            
            disciplinas_formatadas.append(Disciplina.model_validate(disc))
        
        return [d.model_dump() for d in disciplinas_formatadas]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

### ENDPOINT PARA ATUALIZAR DISCIPLINA ###
@router.put("/update/{disciplina_id}", response_model=Disciplina)
def update_disciplina(disciplina_id: uuid.UUID, disciplina_data: DisciplinaUpdate, current_user: dict = Depends(require_admin_or_coordenador)):
    try:
        update_payload = disciplina_data.model_dump(exclude_unset=True)

        if not update_payload:
            raise HTTPException(status_code=400, detail="Nenhum dado fornecido para atualização")

        # Atualiza apenas os campos da disciplina (nome, codigo, semestre, ementa, carga_horaria)
        # Relacionamentos com professores são gerenciados através da tabela professordisciplina
        # e devem ser atualizados via endpoint de professores
        response = supabase.table('disciplina').update(update_payload).eq('id_disciplina', str(disciplina_id)).execute()

        if not response.data:
            raise HTTPException(status_code=404, detail="Disciplina não encontrada para atualização.")

        return response.data[0]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

### ENDPOINT PARA DELETAR DISCIPLINA ###
@router.delete("/delete/{disciplina_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_disciplina(disciplina_id: uuid.UUID, current_user: dict = Depends(require_admin_or_coordenador_or_professor)):
    try:
        # Verificar se a disciplina existe antes de deletar
        disciplina_check = supabase.table('disciplina').select('id_disciplina').eq('id_disciplina', str(disciplina_id)).execute()
        
        if not disciplina_check.data:
            raise HTTPException(status_code=404, detail="Disciplina não encontrada para deletar")
        
        # 1. Deletar relacionamentos na tabela professordisciplina primeiro
        try:
            supabase.table('professordisciplina').delete().eq('id_disciplina', str(disciplina_id)).execute()
        except Exception as e:
            print(f"[WARN] Erro ao deletar relacionamentos professor-disciplina: {e}")
        
        # 2. Deletar relacionamentos na tabela alunodisciplina
        try:
            supabase.table('alunodisciplina').delete().eq('id_disciplina', str(disciplina_id)).execute()
        except Exception as e:
            print(f"[WARN] Erro ao deletar relacionamentos aluno-disciplina: {e}")
        
        # 3. Deletar relacionamentos na tabela cursodisciplina
        try:
            supabase.table('cursodisciplina').delete().eq('id_disciplina', str(disciplina_id)).execute()
        except Exception as e:
            print(f"[WARN] Erro ao deletar relacionamentos curso-disciplina: {e}")
        
        # 4. Deletar avaliações relacionadas (se existirem)
        try:
            supabase.table('avaliacao').delete().eq('id_disciplina', str(disciplina_id)).execute()
        except Exception as e:
            print(f"[WARN] Erro ao deletar avaliações relacionadas: {e}")
        
        # 5. Deletar cronogramas relacionados (se existirem)
        try:
            supabase.table('cronograma').delete().eq('id_disciplina', str(disciplina_id)).execute()
        except Exception as e:
            print(f"[WARN] Erro ao deletar cronogramas relacionados: {e}")
        
        # 6. Deletar trabalhos acadêmicos relacionados (se existirem)
        try:
            supabase.table('trabalho_academico').delete().eq('id_disciplina', str(disciplina_id)).execute()
        except Exception as e:
            print(f"[WARN] Erro ao deletar trabalhos acadêmicos relacionados: {e}")
        
        # 7. Deletar base de conhecimento relacionada (se existir)
        try:
            supabase.table('baseconhecimento').delete().eq('id_disciplina', str(disciplina_id)).execute()
        except Exception as e:
            print(f"[WARN] Erro ao deletar base de conhecimento relacionada: {e}")
        
        # 8. Deletar avisos relacionados (se existirem) - opcional, avisos podem existir sem disciplina
        try:
            supabase.table('aviso').delete().eq('id_disciplina', str(disciplina_id)).execute()
        except Exception as e:
            print(f"[WARN] Erro ao deletar avisos relacionados: {e}")
        
        # 9. Deletar a disciplina
        db_response = supabase.table('disciplina').delete().eq('id_disciplina', str(disciplina_id)).execute()

        if not db_response.data:
            raise HTTPException(status_code=404, detail="Disciplina não encontrada para deletar")

        return
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


from fastapi import APIRouter, HTTPException, status, Depends
from ..supabase_client import supabase
from typing import List, Dict
from ..schemas.sch_msg_aluno import MensagemAluno, MensagemAlunoCreate, MensagemAlunoUpdate
from ..dependencies import require_admin_or_coordenador_or_professor, require_all, require_admin_or_coordenador
import uuid
import json
import re
from collections import Counter
from statistics import mean, stdev



# --- ROUTER MENSAGEM DOS ALUNOS ---

router = APIRouter(
    prefix="/mensagens_aluno",
    tags=["Mensagens de Alunos"]
)

# Função para simplificar a conversão dos tópicos
def convert_json_fields(db_data: dict) -> dict:
    if isinstance(db_data.get('topico'), str):
        db_data['topico'] = json.loads(db_data['topico'])

    return db_data


### ENDPOINT PARA CADASTRAR UMA MENSAGEM DE ALUNO ###
@router.post("/", status_code=status.HTTP_201_CREATED, response_model=MensagemAluno)
def create_mensagem_aluno(item: MensagemAlunoCreate, current_user: dict = Depends(require_admin_or_coordenador_or_professor)):
    try:
        # Prepara os dados da mensagem para ser adicionada na tabela "MensagemAluno"
        payload = item.model_dump()

        # Converter a lista de tópicos para o padrão JSON
        if 'topico' in payload:
            payload['topico'] = json.dumps(payload['topico'])

        # Converte a data e hora para o formato que é compatível com o Supabase
        payload['data_hora'] = payload['data_hora'].isoformat()

        # Inserir a mensagem do aluno na tabela MensagemAluno
        db_response = supabase.table("mensagemaluno").insert(payload).execute()

        # Verifica se a inserção foi bem-sucedida
        if not db_response.data:
            raise HTTPException(status_code=500, detail="Erro ao salvar a mensagem do aluno.")

        db_data = db_response.data[0]

        return convert_json_fields(db_data)

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

### ENDPOINT PARA LISTAR TODAS AS MENSAGENS ###
@router.get("/get_lista_msg/", response_model=List[MensagemAluno])
def list_mensagens_aluno(current_user: dict = Depends(require_all)):
    try:
        # Realiza a consulta na tabela "mensagemaluno" ordenando por data_hora decrescente
        response = supabase.table("mensagemaluno").select("*").order("data_hora", desc=True).execute()

        # Processa os dados convertendo os campos JSON
        processed_data = [convert_json_fields(item) for item in response.data]
        return processed_data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

### ENDPOINT PARA ATUALIZAR UMA MENSAGEM ###
# Esse endpoint será usado somente para teste de desenvolvimento
@router.put("/update/{item_id}", response_model=MensagemAluno)
def update_mensagem(item_id: uuid.UUID, item: MensagemAlunoUpdate, current_user: dict = Depends(require_admin_or_coordenador)):
    try:
        # Cria um dicionario apenas com os dados que foram enviados (não none)
        payload = item.model_dump(exclude_unset=True)

        # Converte a data e hora para o formato que é compatível com o Supabase
        if 'data_hora' in payload:
            payload['data_hora'] = payload['data_hora'].isoformat()

        if not payload:
            raise HTTPException(status_code=400, detail="Nenhum dado fornecido para atualização.")

        # Atualiza os dados da mensagem na tabela MensagemAluno
        db_response = supabase.table("mensagemaluno").update(payload).eq('id_mensagem', str(item_id)).execute()

        # Verifica se a atualização foi bem-sucedida
        if not db_response.data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Mensagem com ID '{item_id}' não encontrada.")

        db_data = db_response.data[0]
        return convert_json_fields(db_data)
    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
        

### ENDPOINT PARA DELETAR UMA MENSAGEM DE ALUNO ###
# **Esse endpoint será usado somente para teste de desenvolvimento**
@router.delete("/delete/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_mensagem(item_id: uuid.UUID, current_user: dict = Depends(require_admin_or_coordenador_or_professor)):
    try:
        # Executa o delete no Supabase | tabela = mensagemaluno | identificado da mensagem = id_mensagem
        db_response = supabase.table("mensagemaluno").delete().eq('id_mensagem', str(item_id)).execute()

        # Verifica se algum dado foi retornado (o que significa que algo foi deletado)
        if not db_response.data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Mensagem com ID '{item_id}' não encontrada para deletar.")

        # HTTP 204 não deve retornar nenhum corpo de resposta
        return
    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

def _normalizar_pergunta(pergunta: str) -> str:
    """Normaliza pergunta para agrupamento (remove acentos, lowercase, remove pontuação)"""
    if not pergunta:
        return ""
    # Remove acentos básicos
    pergunta = pergunta.lower().strip()
    # Remove pontuação e espaços extras
    pergunta = re.sub(r'[^\w\s]', '', pergunta)
    pergunta = re.sub(r'\s+', ' ', pergunta)
    return pergunta

def _sao_similares(pergunta1: str, pergunta2: str, threshold: float = 0.7) -> bool:
    """Verifica se duas perguntas são similares usando similaridade de palavras"""
    norm1 = _normalizar_pergunta(pergunta1)
    norm2 = _normalizar_pergunta(pergunta2)
    
    if not norm1 or not norm2:
        return False
    
    palavras1 = set(norm1.split())
    palavras2 = set(norm2.split())
    
    if not palavras1 or not palavras2:
        return False
    
    # Calcula similaridade de Jaccard
    intersecao = len(palavras1 & palavras2)
    uniao = len(palavras1 | palavras2)
    
    if uniao == 0:
        return False
    
    similaridade = intersecao / uniao
    return similaridade >= threshold

### ENDPOINT PARA DASHBOARD DE DÚVIDAS FREQUENTES ###
@router.get("/dashboard/", response_model=Dict)
def get_dashboard_duvidas_frequentes():
    """
    Retorna dados processados para dashboard de dúvidas frequentes.
    Agrupa perguntas similares e aplica filtro de frequência baseado em desvio padrão.
    """
    try:
        # Realiza a consulta na tabela "mensagemaluno" ordenando por data_hora decrescente
        response = supabase.table("mensagemaluno").select("*").order("data_hora", desc=True).execute()
        
        todas_mensagens = [convert_json_fields(item) for item in response.data]
        
        # Agrupar perguntas similares por tópico
        grupos_perguntas = {}  # {topico: {pergunta_normalizada: {pergunta_original, count, ids}}}
        
        for mensagem in todas_mensagens:
            if not isinstance(mensagem, dict):
                continue
                
            pergunta = mensagem.get('primeira_pergunta', '').strip()
            if not pergunta:
                continue
            
            topico = mensagem.get('topico', [])
            if isinstance(topico, list) and len(topico) > 0:
                topico_str = topico[0] if isinstance(topico[0], str) else str(topico[0])
            elif isinstance(topico, str):
                topico_str = topico
            else:
                topico_str = 'Geral'
            
            if topico_str not in grupos_perguntas:
                grupos_perguntas[topico_str] = {}
            
            # Tenta encontrar grupo similar existente
            pergunta_normalizada = _normalizar_pergunta(pergunta)
            grupo_encontrado = None
            
            for pergunta_norm_existente, dados_grupo in grupos_perguntas[topico_str].items():
                if _sao_similares(pergunta, dados_grupo['pergunta_original'], threshold=0.6):
                    grupo_encontrado = pergunta_norm_existente
                    break
            
            if grupo_encontrado:
                # Adiciona ao grupo existente
                grupos_perguntas[topico_str][grupo_encontrado]['count'] += 1
                grupos_perguntas[topico_str][grupo_encontrado]['ids'].append(mensagem.get('id_mensagem'))
            else:
                # Cria novo grupo
                grupos_perguntas[topico_str][pergunta_normalizada] = {
                    'pergunta_original': pergunta,
                    'count': 1,
                    'ids': [mensagem.get('id_mensagem')],
                    'topico': topico_str
                }
        
        # Calcular estatísticas de frequência
        todas_contagens = []
        for topico, grupos in grupos_perguntas.items():
            for grupo_data in grupos.values():
                todas_contagens.append(grupo_data['count'])
        
        if not todas_contagens:
            return {
                "total_geral": 0,
                "topicos": [],
                "duvidas_frequentes": [],
                "estatisticas": {
                    "media": 0,
                    "desvio_padrao": 0,
                    "limiar_frequencia": 0
                }
            }
        
        media_contagens = mean(todas_contagens)
        desvio_padrao_contagens = stdev(todas_contagens) if len(todas_contagens) > 1 else 0
        
        # Limiar de frequência: média + 0.5 * desvio padrão (ou mínimo de 2 ocorrências)
        limiar_frequencia = max(2, int(media_contagens + 0.5 * desvio_padrao_contagens))
        
        # Filtrar apenas dúvidas que passam do limiar
        duvidas_frequentes = []
        topicos_stats = {}  # {topico: {total: int, frequentes: int}}
        
        for topico, grupos in grupos_perguntas.items():
            topicos_stats[topico] = {
                'total': len(grupos),
                'frequentes': 0,
                'count_total': sum(g['count'] for g in grupos.values())
            }
            
            for grupo_data in grupos.values():
                if grupo_data['count'] >= limiar_frequencia:
                    topicos_stats[topico]['frequentes'] += 1
                    duvidas_frequentes.append({
                        'pergunta': grupo_data['pergunta_original'],
                        'count': grupo_data['count'],
                        'topico': topico,
                        'ids': grupo_data['ids'][:5]  # Limita IDs para não sobrecarregar
                    })
        
        # Ordenar dúvidas por frequência
        duvidas_frequentes.sort(key=lambda x: x['count'], reverse=True)
        
        # Preparar dados para gráficos
        topicos_ordenados = sorted(
            topicos_stats.items(),
            key=lambda x: x[1]['count_total'],
            reverse=True
        )
        
        return {
            "total_geral": len(todas_mensagens),
            "total_grupos": sum(len(grupos) for grupos in grupos_perguntas.values()),
            "total_frequentes": len(duvidas_frequentes),
            "topicos": [
                {
                    "nome": topico,
                    "total_grupos": stats['total'],
                    "grupos_frequentes": stats['frequentes'],
                    "count_total": stats['count_total']
                }
                for topico, stats in topicos_ordenados
            ],
            "duvidas_frequentes": duvidas_frequentes,
            "estatisticas": {
                "media": round(media_contagens, 2),
                "desvio_padrao": round(desvio_padrao_contagens, 2),
                "limiar_frequencia": limiar_frequencia,
                "max_count": max(todas_contagens) if todas_contagens else 0,
                "min_count": min(todas_contagens) if todas_contagens else 0
            }
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Um erro inesperado ocorreu: {str(e)}"
        )

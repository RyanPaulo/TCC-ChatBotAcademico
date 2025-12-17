from typing import List, Optional
from datetime import date
from fastapi import APIRouter, HTTPException, status, Depends
from ..supabase_client import supabase
from ..schemas.sch_trabalho_academico import (
    TrabalhoAcademicoCreate,
    TrabalhoAcademico,
    TrabalhoAcademicoUpdate,
    TipoTrabalhoEnum,
)
from ..dependencies import require_admin_or_coordenador, require_admin_or_coordenador_or_professor, require_all
import uuid
import re

# --- ROUTER TRABALHO ACADÊMICO ---

router = APIRouter(
    prefix="/trabalho_academico",
    tags=["Trabalho Acadêmico"],
)


### ENDPOINT PARA CADASTRAR TRABALHO ACADÊMICO ###
@router.post("/", status_code=status.HTTP_201_CREATED, response_model=TrabalhoAcademico)
def create_trabalho_academico(trabalho_data: TrabalhoAcademicoCreate, current_user: dict = Depends(require_admin_or_coordenador_or_professor)):
    try:
        # Prepara os dados do trabalho acadêmico para ser adicionado na tabela "TrabalhoAcademico"
        payload = trabalho_data.model_dump()

        # Converte campos de data/uuid/enum para string onde necessário
        for key, value in payload.items():
            if isinstance(value, (date, uuid.UUID)):
                payload[key] = str(value)
            elif isinstance(value, TipoTrabalhoEnum):
                payload[key] = value.value  # Converte Enum para string

        # Inserir o trabalho acadêmico na tabela TrabalhoAcademico
        response = supabase.table("trabalho_academico").insert(payload).execute()

        # Verifica se a inserção foi bem-sucedida
        if not response.data:
            raise HTTPException(
                status_code=500, detail="Erro ao criar o trabalho acadêmico."
            )

        return response.data[0]
    except Exception as e:
        if "violates foreign key constraint" in str(e).lower():
            raise HTTPException(
                status_code=404,
                detail="Curso, disciplina ou orientador informado não foi encontrado.",
            )
        raise HTTPException(status_code=400, detail=str(e))


def _normalizar_tipo_trabalho(tipo: str) -> Optional[str]:
    """
    Normaliza diferentes variações de tipo de trabalho para o formato esperado no banco.
    Retorna None se o tipo não for reconhecido.
    """
    if not tipo:
        return None
    
    tipo_lower = tipo.lower().strip()
    
    # Mapeamento de variações para valores do banco
    mapeamento = {
        # TC 1
        "tc1": "TC 1",
        "tc 1": "TC 1",
        "trabalho de conclusão 1": "TC 1",
        "trabalho de conclusao 1": "TC 1",
        "tcc 1": "TC 1",
        "tcc1": "TC 1",
        # TC 2
        "tc2": "TC 2",
        "tc 2": "TC 2",
        "trabalho de conclusão 2": "TC 2",
        "trabalho de conclusao 2": "TC 2",
        "tcc 2": "TC 2",
        "tcc2": "TC 2",
        # APS
        "aps": "APS",
        "atividade prática": "APS",
        "atividade pratica": "APS",
        "atividade prática supervisionada": "APS",
        "atividade pratica supervisionada": "APS",
        # Estágio
        "estagio": "estagio",
        "estágio": "estagio",
        # Horas complementares
        "horas_complementares": "horas_complementares",
        "horas complementares": "horas_complementares",
        "hora complementar": "horas_complementares",
        "horas_complementar": "horas_complementares",
        "horas de complementação": "horas_complementares",
        "horas de complementacao": "horas_complementares",
        "hora de complementação": "horas_complementares",
        "hora de complementacao": "horas_complementares",
        "complementares": "horas_complementares",
    }
    
    return mapeamento.get(tipo_lower)


def _converter_numero_para_romano(nome: str) -> str:
    """
    Converte números para algarismos romanos no nome da disciplina.
    Exemplos:
    - "Trabalho de Curso 1" → "Trabalho de Curso I"
    - "Trabalho de Curso 2" → "Trabalho de Curso II"
    """
    if not nome:
        return nome
    
    # Mapeamento de números para romanos (ordem decrescente para evitar conflitos)
    numero_para_romano = {
        "1": "I",
        "2": "II",
        "3": "III",
        "4": "IV",
        "5": "V",
    }
    
    resultado = nome
    # Tentar substituir números no final da string ou seguidos de espaço/fim
    for num, romano in numero_para_romano.items():
        # Padrão mais flexível: número seguido de espaço ou no final
        # Ex: "Curso 2" ou "Curso 2 " ou "Curso 2."
        padrao = r'(\s|^)' + re.escape(num) + r'(\s|$|[^\d])'
        resultado = re.sub(padrao, r'\1' + romano + r'\2', resultado)
    
    return resultado.strip()


def _converter_romano_para_numero(nome: str) -> str:
    """
    Converte algarismos romanos para números no nome da disciplina.
    Exemplos:
    - "Trabalho de Curso I" → "Trabalho de Curso 1"
    - "Trabalho de Curso II" → "Trabalho de Curso 2"
    """
    if not nome:
        return nome
    
    # Mapeamento de romanos para números (ordem decrescente para evitar conflitos)
    romano_para_numero = {
        "III": "3",
        "II": "2",
        "IV": "4",
        "I": "1",
        "V": "5",
    }
    
    resultado = nome
    for romano, num in romano_para_numero.items():
        # Padrão: romano no final ou seguido de espaço/pontuação
        padrao = r'\b' + re.escape(romano) + r'(?=\s|$|[^\w])'
        resultado = re.sub(padrao, num, resultado, flags=re.IGNORECASE)
    
    return resultado.strip()


def _buscar_disciplina_por_nome_flexivel(nome_disciplina: str) -> Optional[dict]:
    """
    Busca disciplina por nome de forma flexível usando ilike (como no endpoint get_ementa).
    Tenta buscar com o nome original e com variações (número ↔ romano).
    """
    # Preparar variações do nome
    nome_com_romano = _converter_numero_para_romano(nome_disciplina)
    nome_com_numero = _converter_romano_para_numero(nome_disciplina)
    
    # Lista de nomes para tentar (sem duplicatas)
    nomes_para_tentar = [nome_disciplina]
    if nome_com_romano != nome_disciplina:
        nomes_para_tentar.append(nome_com_romano)
    if nome_com_numero != nome_disciplina and nome_com_numero not in nomes_para_tentar:
        nomes_para_tentar.append(nome_com_numero)
    
    # Tentar buscar com cada variação usando ilike (busca parcial case-insensitive)
    # Similar ao endpoint get_ementa/{nome_disciplina}
    for nome in nomes_para_tentar:
        try:
            response = (
                supabase.table("disciplina")
                .select("id_disciplina, nome_disciplina")
                .ilike("nome_disciplina", f"%{nome}%")
                .limit(1)
                .execute()
            )
            if response.data and len(response.data) > 0:
                return response.data[0]
        except Exception:
            # Continuar tentando outras variações
            continue
    
    return None


### ENDPOINT PARA BUSCAR TRABALHO POR TIPO E NOME DA DISCIPLINA ###
@router.get("/get_tipo_e_disciplina", response_model=TrabalhoAcademico)
def get_trabalho_academico_by_tipo_e_disciplina(tipo: str, nome_disciplina: str, current_user: dict = Depends(require_all)):
    try:
        # Normalizar o tipo de trabalho para o formato esperado no banco
        tipo_normalizado = _normalizar_tipo_trabalho(tipo)
        
        if not tipo_normalizado:
            raise HTTPException(
                status_code=400,
                detail=f"Tipo de trabalho '{tipo}' não reconhecido. Tipos válidos: TC 1, TC 2, APS, estagio, horas_complementares"
            )
        
        # Buscar o id_disciplina usando busca flexível (aceita variações como números/romanos)
        disciplina_encontrada = _buscar_disciplina_por_nome_flexivel(nome_disciplina)

        if not disciplina_encontrada:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=f"Disciplina '{nome_disciplina}' não encontrada."
            )

        id_disciplina = disciplina_encontrada["id_disciplina"]
        nome_disciplina_encontrada = disciplina_encontrada.get("nome_disciplina", nome_disciplina)

        # Realiza a consulta na tabela "trabalho_academico" filtrando por tipo e id_disciplina
        response = (
            supabase.table("trabalho_academico")
            .select("*")
            .eq("tipo", tipo_normalizado)
            .eq("id_disciplina", str(id_disciplina))
            .execute()
        )

        # Verifica se a busca retornou algum dado
        if not response.data or len(response.data) == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, 
                detail=f"Trabalho acadêmico do tipo '{tipo_normalizado}' para a disciplina '{nome_disciplina_encontrada}' não encontrado."
            )

        # Se encontrou múltiplos, retornar o primeiro
        return response.data[0]
    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        if "JSON object requested, multiple (or no) rows returned" in str(e):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, 
                detail=f"Trabalho acadêmico do tipo '{tipo_normalizado}' para a disciplina '{nome_disciplina}' não encontrado."
            )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Um erro inesperado ocorreu: {str(e)}"
        )


### ENDPOINT PARA LISTAR TRABALHOS POR TIPO ###
@router.get("/tipo/{tipo}", response_model=List[TrabalhoAcademico])
def get_trabalhos_por_tipo(tipo: str, current_user: dict = Depends(require_all)):
    """
    Lista todos os trabalhos acadêmicos de um determinado tipo.
    Aceita variações do tipo e normaliza automaticamente:
    - TC 1: "tc 1", "tc1", "tcc 1", "tcc1", "trabalho de conclusão 1"
    - TC 2: "tc 2", "tc2", "tcc 2", "tcc2", "trabalho de conclusão 2"
    - APS: "aps", "atividade prática", "atividade pratica"
    - Estágio: "estagio", "estágio"
    - Horas Complementares: "horas complementares", "horas_complementares", "hora complementar", "complementares"
    """
    try:
        # Normalizar o tipo de trabalho para o formato esperado no banco
        # A função _normalizar_tipo_trabalho aceita variações como "horas complementares" → "horas_complementares"
        tipo_normalizado = _normalizar_tipo_trabalho(tipo)
        
        if not tipo_normalizado:
            raise HTTPException(
                status_code=400,
                detail=f"Tipo de trabalho '{tipo}' não reconhecido. Tipos válidos: TC 1, TC 2, APS, estagio, horas_complementares"
            )
        
        # Realiza a consulta na tabela "trabalho_academico" filtrando pelo tipo
        response = (
            supabase.table("trabalho_academico")
            .select("*")
            .eq("tipo", tipo_normalizado)
            .execute()
        )
        
        if not response.data:
            return []
        
        return response.data
    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


### ENDPOINT PARA LISTAR TRABALHOS POR CURSO ###
@router.get("/curso/{curso_id}", response_model=List[TrabalhoAcademico])
def get_trabalhos_por_curso(curso_id: uuid.UUID, current_user: dict = Depends(require_all)):
    try:
        # Realiza a consulta na tabela "trabalho_academico" filtrando pelo id_curso
        response = (
            supabase.table("trabalho_academico")
            .select("*")
            .eq("id_curso", str(curso_id))
            .execute()
        )
        return response.data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


### ENDPOINT PARA LISTAR TRABALHOS POR DISCIPLINA ###
@router.get("/disciplina/{disciplina_id}", response_model=List[TrabalhoAcademico])
def get_trabalhos_por_disciplina(disciplina_id: uuid.UUID, current_user: dict = Depends(require_all)):
    try:
        # Realiza a consulta na tabela "trabalho_academico" filtrando pelo id_disciplina
        response = (
            supabase.table("trabalho_academico")
            .select("*")
            .eq("id_disciplina", str(disciplina_id))
            .execute()
        )
        return response.data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


### ENDPOINT PARA ATUALIZAR UM TRABALHO ACADÊMICO ###
@router.put("/update/{trabalho_id}", response_model=TrabalhoAcademico)
def update_trabalho_academico(trabalho_id: uuid.UUID, trabalho_update_data: TrabalhoAcademicoUpdate, current_user: dict = Depends(require_admin_or_coordenador)):
    try:
        # Cria um dicionario apenas com os dados que foram enviados (não none)
        update_payload = trabalho_update_data.model_dump(exclude_unset=True)

        if not update_payload:
            raise HTTPException(
                status_code=400, detail="Nenhum dado fornecido para atualização."
            )

        # Converte campos de data/uuid/enum para string onde necessário
        for key, value in update_payload.items():
            if isinstance(value, (date, uuid.UUID)):
                update_payload[key] = str(value)
            elif isinstance(value, TipoTrabalhoEnum):
                update_payload[key] = value.value  # Converte Enum para string

        # Atualiza os dados do trabalho acadêmico na tabela TrabalhoAcademico
        response = (
            supabase.table("trabalho_academico")
            .update(update_payload)
            .eq("id_trabalho", str(trabalho_id))
            .execute()
        )

        # Verifica se a atualização foi bem-sucedida
        if not response.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Trabalho acadêmico não encontrado."
            )

        return response.data[0]
    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        if "violates foreign key constraint" in str(e).lower():
            raise HTTPException(
                status_code=404,
                detail="Curso, disciplina ou orientador informado não foi encontrado.",
            )
        raise HTTPException(status_code=500, detail=str(e))


### ENDPOINT PARA DELETAR UM TRABALHO ACADÊMICO ###
@router.delete("/delete/{trabalho_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_trabalho_academico(
    trabalho_id: uuid.UUID,
    current_user: dict = Depends(require_admin_or_coordenador),
):
    try:
        # Executa o delete no Supabase | tabela = trabalho_academico | identificado do trabalho = id_trabalho
        response = (
            supabase.table("trabalho_academico")
            .delete()
            .eq("id_trabalho", str(trabalho_id))
            .execute()
        )

        # Verifica se algum dado foi retornado (o que significa que algo foi deletado)
        if not response.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Trabalho acadêmico não encontrado para deletar."
            )

        # HTTP 204 não deve retornar nenhum corpo de resposta
        return
    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))




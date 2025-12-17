from fastapi import APIRouter, UploadFile, File, HTTPException, status, Form, Depends
import os
import shutil
import json
import uuid
import re
import unicodedata
import requests
import google.generativeai as genai
from ..config import settings
from ..supabase_client import supabase
from ..dependencies import require_admin_or_coordenador_or_professor

router = APIRouter(
    prefix="/documentos",
    tags=["Documentos"],
)


# Pasta temporária para processar arquivos antes de enviar ao Supabase Storage
TEMP_FOLDER_PATH = "./temporary_documents_folder"

# Garante que a pasta temporária exista
os.makedirs(TEMP_FOLDER_PATH, exist_ok=True)

# Nome do bucket no Supabase Storage
BUCKET_NAME = "documentos"


# Configura o Gemini (reutiliza mesma chave do projeto)
genai.configure(api_key=settings.GOOGLE_API_KEY)
gemini_model = genai.GenerativeModel("gemini-2.5-flash")


def _extrair_disciplina_e_categoria(nome_arquivo: str) -> tuple[str, str]:
    """
    Replica a lógica do metadata_enricher:
    DISCIPLINA-CATEGORIA-NOME.ext
    """
    base_name = os.path.splitext(nome_arquivo)[0]
    partes = base_name.split("-")
    if len(partes) < 2:
        print(
            f"   [ERRO] Nome do arquivo '{nome_arquivo}' fora do padrão. Usando valores padrão."
        )
        return "desconhecida", "Outros"

    nome_disciplina = partes[0]
    categoria = partes[1] if len(partes) > 1 else "Geral"
    return nome_disciplina, categoria.replace("_", " ")


def _buscar_id_disciplina_por_nome(nome_disciplina: str) -> str | None:
    """
    Busca o UUID de uma disciplina diretamente no Supabase pela coluna nome_disciplina.
    """
    print(
        f"   [Busca] Procurando ID para a disciplina '{nome_disciplina}' na tabela 'disciplina'..."
    )
    try:
        # Usamos limit(1) em vez de .single() para evitar erro quando não há linhas
        response = (
            supabase.table("disciplina")
            .select("id_disciplina")
            .eq("nome_disciplina", nome_disciplina)
            .limit(1)
            .execute()
        )

        rows = response.data or []
        if rows:
            disciplina_id = rows[0].get("id_disciplina")
            if disciplina_id:
                print(f"   [Busca] ID encontrado: {disciplina_id}")
                return disciplina_id

        print("   [Busca] Nenhuma disciplina encontrada com esse nome (isso é esperado se for 'desconhecida').")
        return None
    except Exception as e:
        print(f"   [ERRO Busca] Erro ao buscar disciplina: {e}")
        return None


def _buscar_id_curso_por_nome(nome_curso: str) -> str | None:
    """
    Busca o UUID de um curso diretamente no Supabase pela coluna nome_curso.
    """
    print(
        f"   [Busca] Procurando ID para o curso '{nome_curso}' na tabela 'curso'..."
    )
    try:
        # Usamos limit(1) em vez de .single() para evitar erro quando não há linhas
        response = (
            supabase.table("curso")
            .select("id_curso")
            .eq("nome_curso", nome_curso)
            .limit(1)
            .execute()
        )

        rows = response.data or []
        if rows:
            curso_id = rows[0].get("id_curso")
            if curso_id:
                print(f"   [Busca] ID do curso encontrado: {curso_id}")
                return curso_id

        print(f"   [Busca] Nenhum curso encontrado com o nome '{nome_curso}'.")
        return None
    except Exception as e:
        print(f"   [ERRO Busca] Erro ao buscar curso: {e}")
        return None


def _normalizar_tipo_trabalho(tipo: str) -> str:
    """
    Normaliza o tipo de trabalho para corresponder aos valores do enum no banco.
    Mapeia valores comuns para os valores exatos do enum.
    """
    tipo_lower = tipo.strip().lower()
    
    # Mapeamento de valores comuns para valores do enum
    mapeamento = {
        "tcc": "TC 1",  # ou "TC 2" dependendo do caso
        "tc1": "TC 1",
        "tc 1": "TC 1",
        "tc2": "TC 2",
        "tc 2": "TC 2",
        "aps": "APS",
        "APS": "APS",
        "estagio": "estagio",
        "estágio": "estagio",
        "hora_complementares": "horas_complementares",
        "horas_complementares": "horas_complementares",
        "hora complementares": "horas_complementares",
        "horas complementares": "horas_complementares",
    }
    
    # Se encontrar no mapeamento, retorna o valor mapeado
    if tipo_lower in mapeamento:
        return mapeamento[tipo_lower]
    
    # Se não encontrar, tenta capitalizar (para "APS" -> "APS")
    return tipo.strip().upper() if tipo_lower == "aps" else tipo.strip()


def _buscar_id_trabalho_por_tipo_e_curso(tipo_trabalho: str, id_curso: str) -> str | None:
    """
    Busca o UUID de um trabalho acadêmico diretamente no Supabase pela coluna tipo e id_curso.
    Usa comparação exata (eq) pois a coluna tipo pode ser um enum.
    """
    print(
        f"   [Busca] Procurando ID para o trabalho do tipo '{tipo_trabalho}' e curso '{id_curso}' na tabela 'trabalho_academico'..."
    )
    try:
        # Normaliza o tipo para corresponder ao valor do enum
        tipo_normalizado = _normalizar_tipo_trabalho(tipo_trabalho)
        print(f"   [Busca] Tipo normalizado: '{tipo_normalizado}'")
        
        # Usamos eq para comparação exata (necessário para enums)
        response = (
            supabase.table("trabalho_academico")
            .select("id_trabalho")
            .eq("tipo", tipo_normalizado)
            .eq("id_curso", id_curso)
            .limit(1)
            .execute()
        )

        rows = response.data or []
        if rows:
            trabalho_id = rows[0].get("id_trabalho")
            if trabalho_id:
                print(f"   [Busca] ID do trabalho encontrado: {trabalho_id}")
                return trabalho_id

        print(f"   [Busca] Nenhum trabalho encontrado com o tipo '{tipo_normalizado}' para o curso '{id_curso}'.")
        return None
    except Exception as e:
        print(f"   [ERRO Busca] Erro ao buscar trabalho acadêmico: {e}")
        return None


def _buscar_id_trabalho_por_tipo_e_disciplina(tipo_trabalho: str, id_disciplina: str) -> str | None:
    """
    Busca o UUID de um trabalho acadêmico diretamente no Supabase pela coluna tipo e id_disciplina.
    Usa comparação exata (eq) pois a coluna tipo pode ser um enum.
    """
    print(
        f"   [Busca] Procurando ID para o trabalho do tipo '{tipo_trabalho}' e disciplina '{id_disciplina}' na tabela 'trabalho_academico'..."
    )
    try:
        # Normaliza o tipo para corresponder ao valor do enum
        tipo_normalizado = _normalizar_tipo_trabalho(tipo_trabalho)
        print(f"   [Busca] Tipo normalizado: '{tipo_normalizado}'")
        
        # Usamos eq para comparação exata (necessário para enums)
        response = (
            supabase.table("trabalho_academico")
            .select("id_trabalho")
            .eq("tipo", tipo_normalizado)
            .eq("id_disciplina", id_disciplina)
            .limit(1)
            .execute()
        )

        rows = response.data or []
        if rows:
            trabalho_id = rows[0].get("id_trabalho")
            if trabalho_id:
                print(f"   [Busca] ID do trabalho encontrado: {trabalho_id}")
                return trabalho_id

        print(f"   [Busca] Nenhum trabalho encontrado com o tipo '{tipo_normalizado}' para a disciplina '{id_disciplina}'.")
        return None
    except Exception as e:
        print(f"   [ERRO Busca] Erro ao buscar trabalho acadêmico: {e}")
        return None


def _buscar_id_trabalho_por_tipo_curso_e_data(tipo_trabalho: str, id_curso: str, data_entrega: str) -> str | None:
    """
    Busca o UUID de um trabalho acadêmico diretamente no Supabase pela coluna tipo, id_curso e data_entrega.
    Usa comparação exata (eq) pois a coluna tipo pode ser um enum.
    Se o tipo for "tcc", tenta buscar tanto "TC 1" quanto "TC 2".
    """
    print(
        f"   [Busca] Procurando ID para o trabalho do tipo '{tipo_trabalho}', curso '{id_curso}' e data_entrega '{data_entrega}' na tabela 'trabalho_academico'..."
    )
    try:
        tipo_lower = tipo_trabalho.strip().lower()
        
        # Se for "tcc", tenta buscar tanto "TC 1" quanto "TC 2"
        if tipo_lower == "tcc":
            tipos_para_tentar = ["TC 1", "TC 2"]
        else:
            # Normaliza o tipo para corresponder ao valor do enum
            tipo_normalizado = _normalizar_tipo_trabalho(tipo_trabalho)
            tipos_para_tentar = [tipo_normalizado]
        
        # Tenta buscar para cada tipo
        for tipo_normalizado in tipos_para_tentar:
            print(f"   [Busca] Tentando tipo: '{tipo_normalizado}'")
            
            # Usamos eq para comparação exata (necessário para enums e datas)
            response = (
                supabase.table("trabalho_academico")
                .select("id_trabalho")
                .eq("tipo", tipo_normalizado)
                .eq("id_curso", id_curso)
                .eq("data_entrega", data_entrega)
                .limit(1)
                .execute()
            )

            rows = response.data or []
            if rows:
                trabalho_id = rows[0].get("id_trabalho")
                if trabalho_id:
                    print(f"   [Busca] ID do trabalho encontrado: {trabalho_id} (tipo: '{tipo_normalizado}')")
                    return trabalho_id

        print(f"   [Busca] Nenhum trabalho encontrado com o tipo '{tipo_trabalho}' (tentou: {tipos_para_tentar}), curso '{id_curso}' e data_entrega '{data_entrega}'.")
        return None
    except Exception as e:
        print(f"   [ERRO Busca] Erro ao buscar trabalho acadêmico: {e}")
        return None


def _verificar_ou_criar_bucket(bucket_name: str) -> bool:
    """
    Verifica se o bucket existe e tenta criá-lo se não existir.
    Retorna True se o bucket existe ou foi criado com sucesso.
    """
    try:
        # Tenta listar o bucket para verificar se existe
        buckets = supabase.storage.list_buckets()
        bucket_exists = any(b.name == bucket_name for b in buckets)
        
        if bucket_exists:
            print(f"   [Storage] Bucket '{bucket_name}' já existe.")
            return True
        
        # Se não existe, tenta criar via API REST
        print(f"   [Storage] Bucket '{bucket_name}' não encontrado. Tentando criar...")
        create_url = f"{settings.SUPABASE_URL}/storage/v1/bucket"
        
        headers = {
            "Authorization": f"Bearer {settings.SUPABASE_SERVICE_KEY}",
            "apikey": settings.SUPABASE_SERVICE_KEY,
            "Content-Type": "application/json"
        }
        
        payload = {
            "name": bucket_name,
            "public": True,  # Torna o bucket público para facilitar acesso
            "file_size_limit": None,
            "allowed_mime_types": None
        }
        
        create_response = requests.post(create_url, json=payload, headers=headers, timeout=10)
        
        if create_response.status_code in [200, 201]:
            print(f"   [Storage] Bucket '{bucket_name}' criado com sucesso!")
            return True
        else:
            print(f"   [Storage] Aviso: Não foi possível criar o bucket (pode já existir): {create_response.status_code}")
            # Mesmo se não conseguir criar, tenta continuar (pode ser que já exista)
            return True
            
    except Exception as e:
        print(f"   [Storage] Aviso ao verificar/criar bucket: {e}")
        # Continua mesmo se houver erro (o bucket pode já existir)
        return True


def _normalizar_nome_arquivo(nome_arquivo: str) -> str:
    """
    Normaliza o nome do arquivo para ser compatível com Supabase Storage.
    Remove acentos, espaços e caracteres especiais, mantendo apenas alfanuméricos, hífens e underscores.
    """
    # Separa nome e extensão
    nome_base, extensao = os.path.splitext(nome_arquivo)
    
    # Remove acentos e normaliza para ASCII
    nome_normalizado = unicodedata.normalize('NFKD', nome_base)
    nome_normalizado = ''.join(c for c in nome_normalizado if not unicodedata.combining(c))
    
    # Remove caracteres especiais, mantém apenas alfanuméricos, hífens e underscores
    nome_normalizado = re.sub(r'[^a-zA-Z0-9_-]', '_', nome_normalizado)
    
    # Remove underscores múltiplos
    nome_normalizado = re.sub(r'_+', '_', nome_normalizado)
    
    # Remove underscores no início e fim
    nome_normalizado = nome_normalizado.strip('_')
    
    # Se ficar vazio, usa um nome padrão
    if not nome_normalizado:
        nome_normalizado = "documento"
    
    # Adiciona UUID para evitar conflitos e retorna com extensão
    nome_final = f"{nome_normalizado}_{uuid.uuid4().hex[:8]}{extensao}"
    
    return nome_final


def _upload_para_supabase_storage(caminho_arquivo: str, nome_arquivo: str) -> str:
    """
    Faz upload do arquivo para o Supabase Storage usando um nome normalizado.
    Retorna a URL pública.
    Usa a API REST diretamente com service key para contornar RLS.
    """
    print(f"   [Storage] 1. Fazendo upload do arquivo para o bucket '{BUCKET_NAME}'...")
    
    # Verifica se o bucket existe antes de tentar fazer upload
    _verificar_ou_criar_bucket(BUCKET_NAME)
    
    try:
        # Lê o arquivo em bytes
        with open(caminho_arquivo, "rb") as f:
            file_data = f.read()
        
        # Normaliza o nome do arquivo para ser compatível com Supabase Storage
        nome_arquivo_normalizado = _normalizar_nome_arquivo(nome_arquivo)
        
        print(f"   [Storage] Nome original: {nome_arquivo}")
        print(f"   [Storage] Nome normalizado: {nome_arquivo_normalizado}")
        
        # Tenta primeiro com o cliente Supabase (método padrão)
        try:
            response = supabase.storage.from_(BUCKET_NAME).upload(
                path=nome_arquivo_normalizado,
                file=file_data,
                file_options={
                    "content-type": "application/octet-stream",
                    "upsert": "true",
                    "x-upsert": "true"  # Garante upsert
                }
            )
            print(f"   [Storage] Upload realizado com sucesso usando cliente Supabase")
        except Exception as upload_error:
            # Se der erro de RLS, usa a API REST diretamente com service key
            error_str = str(upload_error)
            if "row-level security" in error_str.lower() or "403" in error_str or "Unauthorized" in error_str:
                print(f"   [Storage] Erro de RLS detectado. Tentando upload via API REST com service key...")
                
                # Usa a API REST do Supabase Storage diretamente com service key
                # Isso deve contornar o RLS
                storage_url = f"{settings.SUPABASE_URL}/storage/v1/object/{BUCKET_NAME}/{nome_arquivo_normalizado}"
                
                headers = {
                    "Authorization": f"Bearer {settings.SUPABASE_SERVICE_KEY}",
                    "apikey": settings.SUPABASE_SERVICE_KEY,
                    "Content-Type": "application/octet-stream",
                    "x-upsert": "true"
                }
                
                try:
                    # Faz upload via API REST
                    upload_response = requests.post(
                        storage_url,
                        data=file_data,
                        headers=headers,
                        timeout=30
                    )
                    
                    if upload_response.status_code not in [200, 201]:
                        error_detail = upload_response.text
                        print(f"   [Storage] Erro na API REST: {upload_response.status_code} - {error_detail}")
                        raise HTTPException(
                            status_code=status.HTTP_403_FORBIDDEN,
                            detail=f"Erro ao fazer upload via API REST: {upload_response.status_code}. "
                                   f"Verifique as políticas RLS do bucket '{BUCKET_NAME}' no Supabase Dashboard. "
                                   f"Erro: {error_detail}",
                        )
                    
                    print(f"   [Storage] Upload realizado com sucesso via API REST")
                except requests.exceptions.RequestException as api_error:
                    print(f"   [Storage] Erro na requisição API REST: {api_error}")
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail=f"Erro ao fazer upload via API REST: {str(api_error)}",
                    )
            else:
                # Se não for erro de RLS, propaga o erro original
                raise
        
        # Obtém a URL pública do arquivo
        # get_public_url retorna um dicionário com a chave 'publicUrl' ou a URL diretamente
        try:
            public_url_response = supabase.storage.from_(BUCKET_NAME).get_public_url(nome_arquivo_normalizado)
            
            # Se for um dicionário, extrai a URL; se for string, usa diretamente
            if isinstance(public_url_response, dict):
                url_documento = public_url_response.get("publicUrl") or public_url_response.get("url") or str(public_url_response)
            else:
                url_documento = str(public_url_response)
        except Exception as url_error:
            # Se não conseguir a URL pública, constrói manualmente
            print(f"   [Storage] Aviso: Não foi possível obter URL pública automaticamente: {url_error}")
            url_documento = f"{settings.SUPABASE_URL}/storage/v1/object/public/{BUCKET_NAME}/{nome_arquivo_normalizado}"
        
        print(f"   [Storage] 2. Arquivo enviado com sucesso!")
        print(f"   [Storage] 3. URL pública: {url_documento}")
        
        return url_documento
        
    except HTTPException:
        # Re-propaga HTTPExceptions
        raise
    except Exception as e:
        print(f"   [ERRO Storage] Falha ao fazer upload: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao fazer upload do arquivo para o Supabase Storage: {e}",
        )


def _processar_com_gemini(caminho_arquivo: str, content_type: str) -> dict:
    """
    Lê o arquivo e pede para o Gemini gerar:
    - resumo (conteudo_processado)
    - palavras_chave (lista de strings)

    Retorna um dicionário já pronto para ser usado.
    """
    print("   [Gemini] 1. Enviando documento para o Gemini para processamento...")

    # Faz upload do arquivo para o Gemini como input multimodal
    try:
        with open(caminho_arquivo, "rb") as f:
            uploaded_file = genai.upload_file(f, mime_type=content_type)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Falha ao enviar arquivo para o Gemini: {e}",
        )

    prompt = """
Você é um assistente acadêmico.
Leia o documento fornecido e responda ESTRITAMENTE em JSON válido, sem comentários nem texto extra.
O formato DEVE ser exatamente:
{
  "resumo": "um resumo em português, com 3 a 8 frases, bem objetivas.",
  "palavras_chave": ["keyword1", "keyword2", "..."]
}

Regras importantes:
- Não inclua nenhum outro campo além de "resumo" e "palavras_chave".
- "palavras_chave" deve ser uma lista de strings curtas (1 a 3 palavras cada).
"""

    try:
        response = gemini_model.generate_content([prompt, uploaded_file])
        raw_text = response.text.strip()
        print(f"   [Gemini] 2. Resposta bruta do modelo:\n{raw_text[:400]}...")
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao comunicar com a API do Gemini: {e}",
        )

    # Às vezes o modelo devolve ```json ... ```, então limpamos isso
    if raw_text.startswith("```"):
        raw_text = raw_text.strip("`")
        # remove possível prefixo "json\n"
        if raw_text.lower().startswith("json"):
            raw_text = raw_text[4:]

    try:
        data = json.loads(raw_text)
    except json.JSONDecodeError as e:
        print(f"   [Gemini] 3. ERRO ao fazer parse do JSON: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Falha ao interpretar resposta do Gemini como JSON: {e}",
        )

    resumo = data.get("resumo", "").strip()
    palavras_chave = data.get("palavras_chave") or []

    if not isinstance(palavras_chave, list):
        palavras_chave = [str(palavras_chave)]

    print("   [Gemini] 4. Resumo gerado:")
    print(f"       {resumo[:300]}...")
    print("   [Gemini] 5. Palavras-chave extraídas:")
    print(f"       {palavras_chave}")

    return {
        "resumo": resumo,
        "palavras_chave": palavras_chave,
    }


@router.post("/upload_disciplina", status_code=status.HTTP_201_CREATED)
async def upload_documento(
    file: UploadFile = File(...),
    nome_disciplina: str = Form(..., description="Nome exato da disciplina cadastrada"),
    current_user: dict = Depends(require_admin_or_coordenador_or_professor),
):
    # Validação básica do tipo de arquivo (opcional, mas recomendado)
    allowed_content_types = [
        "application/pdf",  # .pdf
        "text/plain",  # .txt
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",  # .docx
        "application/msword",  # .doc
    ]
    if file.content_type not in allowed_content_types:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Tipo de arquivo '{file.content_type}' não suportado. Use PDF, TXT ou DOCX.",
        )

    try:
        # Caminho temporário onde o arquivo será salvo para processamento
        destination_path = os.path.join(TEMP_FOLDER_PATH, file.filename)

        print(f"Recebendo arquivo: {file.filename}")
        print(f"Salvando temporariamente em: {os.path.abspath(destination_path)}")

        # Salva o arquivo temporariamente no disco para processamento
        with open(destination_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # 1) Usar o nome da disciplina informado pelo usuário
        disciplina_id = _buscar_id_disciplina_por_nome(nome_disciplina.strip())

        # 2) Processar o conteúdo com o Gemini (resumo + palavras-chave)
        resultado_gemini = _processar_com_gemini(destination_path, file.content_type)

        # 2.1) Deixar a "categoria" a cargo do Gemini:
        #      usamos a primeira palavra-chave como categoria principal, se existir.
        palavras_chave = resultado_gemini["palavras_chave"]
        categoria = palavras_chave[0] if palavras_chave else "Geral"

        # 3) Fazer upload do arquivo para o Supabase Storage
        url_documento = _upload_para_supabase_storage(destination_path, file.filename)

        # 4) Remover arquivo temporário após upload bem-sucedido
        try:
            os.remove(destination_path)
            print(f"   [Limpeza] Arquivo temporário removido: {file.filename}")
        except Exception as e:
            print(f"   [AVISO] Não foi possível remover arquivo temporário: {e}")

        # 5) Montar payload para a tabela baseconhecimento
        payload_base = {
            "nome_arquivo_origem": file.filename,
            "conteudo_processado": resultado_gemini["resumo"],
            "palavra_chave": json.dumps(palavras_chave),
            "categoria": categoria,
            "status": "publicado",
            "id_disciplina": str(disciplina_id) if disciplina_id else None,
            "url_documento": url_documento,
        }

        print("   [API] 6. Salvando conteúdo na tabela 'baseconhecimento'...")
        db_response = (
            supabase.table("baseconhecimento").insert(payload_base).execute()
        )

        if not db_response.data:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Erro ao salvar na base de conhecimento.",
            )

        registro = db_response.data[0]
        print(
            f"   [API] 7. Salvo com sucesso na base de conhecimento (id_conhecimento={registro.get('id_conhecimento')})."
        )

        return {
            "message": f"Arquivo '{file.filename}' recebido, processado pelo Gemini, enviado para o Supabase Storage e salvo na base de conhecimento.",
            "filename": file.filename,
            "content_type": file.content_type,
            "url_documento": url_documento,
            "base_conhecimento": {
                "id_conhecimento": registro.get("id_conhecimento"),
                "categoria": categoria,
                "id_disciplina": disciplina_id,
                "resumo": resultado_gemini["resumo"],
                "palavra_chave": resultado_gemini["palavras_chave"],
                "url_documento": url_documento,
            },
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ocorreu um erro ao processar o arquivo: {e}",
        )
    finally:
        # Fecha o arquivo para liberar recursos
        await file.close()


@router.post("/upload_tcc", status_code=status.HTTP_201_CREATED)
async def upload_tcc(
    file: UploadFile = File(...),
    tipo: str = Form(..., description="Tipo do trabalho acadêmico (ex: tcc, aps, estagio, hora_complementares)"),
    nome_curso: str = Form(..., description="Nome exato do curso cadastrado"),
    data: str = Form(..., description="Data de entrega no formato YYYY-MM-DD (ex: 2025-11-06)"),
    current_user: dict = Depends(require_admin_or_coordenador_or_professor),
):
    # Validação básica do tipo de arquivo
    allowed_content_types = [
        "application/pdf",  # .pdf
        "text/plain",  # .txt
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",  # .docx
        "application/msword",  # .doc
    ]
    if file.content_type not in allowed_content_types:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Tipo de arquivo '{file.content_type}' não suportado. Use PDF, TXT ou DOCX.",
        )

    try:
        destination_path = os.path.join(TEMP_FOLDER_PATH, file.filename)

        print(f"Recebendo arquivo: {file.filename}")
        print(f"Salvando temporariamente em: {os.path.abspath(destination_path)}")

        with open(destination_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # 1° - Consultar a tabela 'curso' e achar o id_curso com base no 'nome do curso'
        curso_id = _buscar_id_curso_por_nome(nome_curso.strip())
        if not curso_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Nenhum curso encontrado com o nome '{nome_curso}'."
            )

        # 2° - Pegar o 'id_curso' junto com o 'tipo' e 'data_entrega' e consultar a tabela 'trabalho_academico' e pegar o 'id_trabalho'
        trabalho_id = _buscar_id_trabalho_por_tipo_curso_e_data(tipo.strip(), curso_id, data.strip())
        if not trabalho_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Nenhum trabalho acadêmico do tipo '{tipo}' encontrado para o curso '{nome_curso}' com data de entrega '{data}' na tabela trabalho_academico."
            )

        # Processar o conteúdo com o Gemini
        resultado_gemini = _processar_com_gemini(destination_path, file.content_type)

        palavras_chave = resultado_gemini["palavras_chave"]
        categoria = palavras_chave[0] if palavras_chave else "Geral"

        # Fazer upload do arquivo para o Supabase Storage
        url_documento = _upload_para_supabase_storage(destination_path, file.filename)

        # Remover arquivo temporário
        try:
            os.remove(destination_path)
            print(f"   [Limpeza] Arquivo temporário removido: {file.filename}")
        except Exception as e:
            print(f"   [AVISO] Não foi possível remover arquivo temporário: {e}")

        # Montar payload para a tabela baseconhecimento
        payload_base = {
            "nome_arquivo_origem": file.filename,
            "conteudo_processado": resultado_gemini["resumo"],
            "palavra_chave": json.dumps(palavras_chave),
            "categoria": categoria,
            "status": "publicado",
            "id_tcc": str(trabalho_id),
            "url_documento": url_documento,
        }

        print("   [API] 6. Salvando conteúdo na tabela 'baseconhecimento'...")
        db_response = (
            supabase.table("baseconhecimento").insert(payload_base).execute()
        )

        if not db_response.data:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Erro ao salvar na base de conhecimento.",
            )

        registro = db_response.data[0]
        print(
            f"   [API] 7. Salvo com sucesso na base de conhecimento (id_conhecimento={registro.get('id_conhecimento')})."
        )

        return {
            "message": f"Arquivo '{file.filename}' recebido, processado pelo Gemini, enviado para o Supabase Storage e salvo na base de conhecimento.",
            "filename": file.filename,
            "content_type": file.content_type,
            "url_documento": url_documento,
            "base_conhecimento": {
                "id_conhecimento": registro.get("id_conhecimento"),
                "categoria": categoria,
                "id_tcc": trabalho_id,
                "resumo": resultado_gemini["resumo"],
                "palavra_chave": resultado_gemini["palavras_chave"],
                "url_documento": url_documento,
            },
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ocorreu um erro ao processar o arquivo: {e}",
        )
    finally:
        await file.close()


@router.post("/upload_aps", status_code=status.HTTP_201_CREATED)
async def upload_aps(
    file: UploadFile = File(...),
    tipo: str = Form(..., description="Tipo do trabalho acadêmico (ex: tcc, aps, estagio, hora_complementares)"),
    nome_disciplina: str = Form(..., description="Nome exato da disciplina cadastrada"),
    current_user: dict = Depends(require_admin_or_coordenador_or_professor),
):
    # Validação básica do tipo de arquivo
    allowed_content_types = [
        "application/pdf",  # .pdf
        "text/plain",  # .txt
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",  # .docx
        "application/msword",  # .doc
    ]
    if file.content_type not in allowed_content_types:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Tipo de arquivo '{file.content_type}' não suportado. Use PDF, TXT ou DOCX.",
        )

    try:
        destination_path = os.path.join(TEMP_FOLDER_PATH, file.filename)

        print(f"Recebendo arquivo: {file.filename}")
        print(f"Salvando temporariamente em: {os.path.abspath(destination_path)}")

        with open(destination_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # 1° - Consultar a tabela 'disciplina' e achar o id_disciplina com base no 'nome da disciplina'
        disciplina_id = _buscar_id_disciplina_por_nome(nome_disciplina.strip())
        if not disciplina_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Nenhuma disciplina encontrada com o nome '{nome_disciplina}'."
            )

        # 2° - Pegar o 'id_disciplina' junto com o 'tipo' e consultar a tabela 'trabalho_academico' e pegar o 'id_trabalho'
        trabalho_id = _buscar_id_trabalho_por_tipo_e_disciplina(tipo.strip(), disciplina_id)
        if not trabalho_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Nenhum trabalho acadêmico do tipo '{tipo}' encontrado para a disciplina '{nome_disciplina}' na tabela trabalho_academico."
            )

        # Processar o conteúdo com o Gemini
        resultado_gemini = _processar_com_gemini(destination_path, file.content_type)

        palavras_chave = resultado_gemini["palavras_chave"]
        categoria = palavras_chave[0] if palavras_chave else "Geral"

        # Fazer upload do arquivo para o Supabase Storage
        url_documento = _upload_para_supabase_storage(destination_path, file.filename)

        # Remover arquivo temporário
        try:
            os.remove(destination_path)
            print(f"   [Limpeza] Arquivo temporário removido: {file.filename}")
        except Exception as e:
            print(f"   [AVISO] Não foi possível remover arquivo temporário: {e}")

        # Montar payload para a tabela baseconhecimento
        payload_base = {
            "nome_arquivo_origem": file.filename,
            "conteudo_processado": resultado_gemini["resumo"],
            "palavra_chave": json.dumps(palavras_chave),
            "categoria": categoria,
            "status": "publicado",
            "id_aps": str(trabalho_id),
            "url_documento": url_documento,
        }

        print("   [API] 6. Salvando conteúdo na tabela 'baseconhecimento'...")
        db_response = (
            supabase.table("baseconhecimento").insert(payload_base).execute()
        )

        if not db_response.data:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Erro ao salvar na base de conhecimento.",
            )

        registro = db_response.data[0]
        print(
            f"   [API] 7. Salvo com sucesso na base de conhecimento (id_conhecimento={registro.get('id_conhecimento')})."
        )

        return {
            "message": f"Arquivo '{file.filename}' recebido, processado pelo Gemini, enviado para o Supabase Storage e salvo na base de conhecimento.",
            "filename": file.filename,
            "content_type": file.content_type,
            "url_documento": url_documento,
            "base_conhecimento": {
                "id_conhecimento": registro.get("id_conhecimento"),
                "categoria": categoria,
                "id_aps": trabalho_id,
                "resumo": resultado_gemini["resumo"],
                "palavra_chave": resultado_gemini["palavras_chave"],
                "url_documento": url_documento,
            },
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ocorreu um erro ao processar o arquivo: {e}",
        )
    finally:
        await file.close()


@router.post("/upload_estagio", status_code=status.HTTP_201_CREATED)
async def upload_estagio(
    file: UploadFile = File(...),
    tipo: str = Form(..., description="Tipo do trabalho acadêmico (ex: tcc, aps, estagio, hora_complementares)"),
    nome_curso: str = Form(..., description="Nome exato do curso cadastrado"),
    current_user: dict = Depends(require_admin_or_coordenador_or_professor),
):
    # Validação básica do tipo de arquivo
    allowed_content_types = [
        "application/pdf",  # .pdf
        "text/plain",  # .txt
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",  # .docx
        "application/msword",  # .doc
    ]
    if file.content_type not in allowed_content_types:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Tipo de arquivo '{file.content_type}' não suportado. Use PDF, TXT ou DOCX.",
        )

    try:
        destination_path = os.path.join(TEMP_FOLDER_PATH, file.filename)

        print(f"Recebendo arquivo: {file.filename}")
        print(f"Salvando temporariamente em: {os.path.abspath(destination_path)}")

        with open(destination_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # 1° - Consultar a tabela 'curso' e achar o id_curso com base no 'nome do curso'
        curso_id = _buscar_id_curso_por_nome(nome_curso.strip())
        if not curso_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Nenhum curso encontrado com o nome '{nome_curso}'."
            )

        # 2° - Pegar o 'id_curso' junto com o 'tipo' e consultar a tabela 'trabalho_academico' e pegar o 'id_trabalho'
        trabalho_id = _buscar_id_trabalho_por_tipo_e_curso(tipo.strip(), curso_id)
        if not trabalho_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Nenhum trabalho acadêmico do tipo '{tipo}' encontrado para o curso '{nome_curso}' na tabela trabalho_academico."
            )

        # Processar o conteúdo com o Gemini
        resultado_gemini = _processar_com_gemini(destination_path, file.content_type)

        palavras_chave = resultado_gemini["palavras_chave"]
        categoria = palavras_chave[0] if palavras_chave else "Geral"

        # Fazer upload do arquivo para o Supabase Storage
        url_documento = _upload_para_supabase_storage(destination_path, file.filename)

        # Remover arquivo temporário
        try:
            os.remove(destination_path)
            print(f"   [Limpeza] Arquivo temporário removido: {file.filename}")
        except Exception as e:
            print(f"   [AVISO] Não foi possível remover arquivo temporário: {e}")

        # Montar payload para a tabela baseconhecimento
        payload_base = {
            "nome_arquivo_origem": file.filename,
            "conteudo_processado": resultado_gemini["resumo"],
            "palavra_chave": json.dumps(palavras_chave),
            "categoria": categoria,
            "status": "publicado",
            "id_estagio": str(trabalho_id),
            "url_documento": url_documento,
        }

        print("   [API] 6. Salvando conteúdo na tabela 'baseconhecimento'...")
        db_response = (
            supabase.table("baseconhecimento").insert(payload_base).execute()
        )

        if not db_response.data:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Erro ao salvar na base de conhecimento.",
            )

        registro = db_response.data[0]
        print(
            f"   [API] 7. Salvo com sucesso na base de conhecimento (id_conhecimento={registro.get('id_conhecimento')})."
        )

        return {
            "message": f"Arquivo '{file.filename}' recebido, processado pelo Gemini, enviado para o Supabase Storage e salvo na base de conhecimento.",
            "filename": file.filename,
            "content_type": file.content_type,
            "url_documento": url_documento,
            "base_conhecimento": {
                "id_conhecimento": registro.get("id_conhecimento"),
                "categoria": categoria,
                "id_estagio": trabalho_id,
                "resumo": resultado_gemini["resumo"],
                "palavra_chave": resultado_gemini["palavras_chave"],
                "url_documento": url_documento,
            },
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ocorreu um erro ao processar o arquivo: {e}",
        )
    finally:
        await file.close()


@router.post("/upload_hora_complementares", status_code=status.HTTP_201_CREATED)
async def upload_hora_complementares(
    file: UploadFile = File(...),
    tipo: str = Form(..., description="Tipo do trabalho acadêmico (ex: tcc, aps, estagio, hora_complementares)"),
    nome_curso: str = Form(..., description="Nome exato do curso cadastrado"),
    current_user: dict = Depends(require_admin_or_coordenador_or_professor),
):
    # Validação básica do tipo de arquivo
    allowed_content_types = [
        "application/pdf",  # .pdf
        "text/plain",  # .txt
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",  # .docx
        "application/msword",  # .doc
    ]
    if file.content_type not in allowed_content_types:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Tipo de arquivo '{file.content_type}' não suportado. Use PDF, TXT ou DOCX.",
        )

    try:
        destination_path = os.path.join(TEMP_FOLDER_PATH, file.filename)

        print(f"Recebendo arquivo: {file.filename}")
        print(f"Salvando temporariamente em: {os.path.abspath(destination_path)}")

        with open(destination_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # 1° - Consultar a tabela 'curso' e achar o id_curso com base no 'nome do curso'
        curso_id = _buscar_id_curso_por_nome(nome_curso.strip())
        if not curso_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Nenhum curso encontrado com o nome '{nome_curso}'."
            )

        # 2° - Pegar o 'id_curso' junto com o 'tipo' e consultar a tabela 'trabalho_academico' e pegar o 'id_trabalho'
        trabalho_id = _buscar_id_trabalho_por_tipo_e_curso(tipo.strip(), curso_id)
        if not trabalho_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Nenhum trabalho acadêmico do tipo '{tipo}' encontrado para o curso '{nome_curso}' na tabela trabalho_academico."
            )

        # Processar o conteúdo com o Gemini
        resultado_gemini = _processar_com_gemini(destination_path, file.content_type)

        palavras_chave = resultado_gemini["palavras_chave"]
        categoria = palavras_chave[0] if palavras_chave else "Geral"

        # Fazer upload do arquivo para o Supabase Storage
        url_documento = _upload_para_supabase_storage(destination_path, file.filename)

        # Remover arquivo temporário
        try:
            os.remove(destination_path)
            print(f"   [Limpeza] Arquivo temporário removido: {file.filename}")
        except Exception as e:
            print(f"   [AVISO] Não foi possível remover arquivo temporário: {e}")

        # Montar payload para a tabela baseconhecimento
        payload_base = {
            "nome_arquivo_origem": file.filename,
            "conteudo_processado": resultado_gemini["resumo"],
            "palavra_chave": json.dumps(palavras_chave),
            "categoria": categoria,
            "status": "publicado",
            "id_horas_complementares": str(trabalho_id),
            "url_documento": url_documento,
        }

        print("   [API] 6. Salvando conteúdo na tabela 'baseconhecimento'...")
        db_response = (
            supabase.table("baseconhecimento").insert(payload_base).execute()
        )

        if not db_response.data:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Erro ao salvar na base de conhecimento.",
            )

        registro = db_response.data[0]
        print(
            f"   [API] 7. Salvo com sucesso na base de conhecimento (id_conhecimento={registro.get('id_conhecimento')})."
        )

        return {
            "message": f"Arquivo '{file.filename}' recebido, processado pelo Gemini, enviado para o Supabase Storage e salvo na base de conhecimento.",
            "filename": file.filename,
            "content_type": file.content_type,
            "url_documento": url_documento,
            "base_conhecimento": {
                "id_conhecimento": registro.get("id_conhecimento"),
                "categoria": categoria,
                "id_horas_complementares": trabalho_id,
                "resumo": resultado_gemini["resumo"],
                "palavra_chave": resultado_gemini["palavras_chave"],
                "url_documento": url_documento,
            },
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ocorreu um erro ao processar o arquivo: {e}",
        )
    finally:
        await file.close()


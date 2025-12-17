from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
import google.generativeai as genai
import requests
import os
import tempfile
from ..config import settings
from ..supabase_client import supabase
from ..dependencies import require_all, require_aluno, require_admin_or_coordenador_or_professor

# from ..dependencies import 


# Carrega a chave da API do Gemini
genai.configure(api_key=settings.GOOGLE_API_KEY)
gemini_model = genai.GenerativeModel("gemini-2.5-flash")

router = APIRouter(
    prefix="/ia",
    tags=["Serviços de IA"],
)


class GenerationRequest(BaseModel):
    pergunta: str
    contexto: str | None = None


def _buscar_contextos_da_base(pergunta: str) -> tuple[list[str], list[dict]]:
    """
    Busca contexto na base de conhecimento de forma abrangente.
    Retorna uma tupla: (lista de contextos de texto, lista de documentos com URL).
    """
    contextos: list[str] = []
    documentos_com_url: list[dict] = []
    registros_processados = set()  # Para evitar duplicatas

    # Normaliza a pergunta para busca
    import re
    pergunta_lower = pergunta.lower().strip()
    # Remove pontuação e extrai palavras-chave (mínimo 3 caracteres, exclui palavras comuns)
    palavras_comuns = {"que", "qual", "quais", "como", "onde", "quando", "por", "para", "com", "sem", "sobre", "este", "esta", "isso", "isso"}
    palavras_raw = re.findall(r'\b\w+\b', pergunta_lower)
    palavras_chave_pergunta = [p for p in palavras_raw if len(p) >= 3 and p not in palavras_comuns]

    print(f"   [Busca] Procurando por: '{pergunta_lower}'")
    print(f"   [Busca] Palavras-chave extraídas: {palavras_chave_pergunta}")

    try:
        # 1) Tenta via função RPC (busca semântica/vetorial) - mas não depende só dela
        try:
            search_response = supabase.rpc(
                "buscar_conteudo", {"query": pergunta}
            ).execute()

            if search_response.data:
                print(f"   [Busca RPC] Encontrados {len(search_response.data)} resultados via RPC")
                for item in search_response.data:
                    id_reg = item.get("id_conhecimento")
                    if id_reg and id_reg not in registros_processados:
                        registros_processados.add(id_reg)
                        conteudo = item.get("conteudo_processado") or item.get("conteudo_original") or ""
                        if conteudo:
                            contextos.append(conteudo)
                        
                        url_doc = item.get("url_documento")
                        if url_doc:
                            documentos_com_url.append({
                                "url_documento": url_doc,
                                "nome_arquivo": item.get("nome_arquivo_origem", "documento"),
                                "id_conhecimento": id_reg
                            })
        except Exception as e:
            print(f"   [Busca RPC] RPC não disponível ou erro: {e}")

        # 2) Busca direta na tabela - SEMPRE executa (não é só fallback)
        # 2.1) Busca em conteudo_processado (busca pela pergunta completa E por termos individuais)
        try:
            # Busca pela pergunta completa
            busca_conteudo = (
                supabase.table("baseconhecimento")
                .select("id_conhecimento, conteudo_processado, url_documento, nome_arquivo_origem, palavra_chave, categoria")
                .ilike("conteudo_processado", f"%{pergunta_lower}%")
                .eq("status", "publicado")
                .limit(10)
                .execute()
            )

            if busca_conteudo.data:
                print(f"   [Busca Conteudo] Encontrados {len(busca_conteudo.data)} resultados em conteudo_processado (pergunta completa)")
                for item in busca_conteudo.data:
                    id_reg = item.get("id_conhecimento")
                    if id_reg and id_reg not in registros_processados:
                        registros_processados.add(id_reg)
                        conteudo = item.get("conteudo_processado", "")
                        if conteudo:
                            contextos.append(conteudo)
                        
                        url_doc = item.get("url_documento")
                        if url_doc:
                            documentos_com_url.append({
                                "url_documento": url_doc,
                                "nome_arquivo": item.get("nome_arquivo_origem", "documento"),
                                "id_conhecimento": id_reg
                            })
            
            # Busca por termos individuais (se houver palavras-chave)
            if palavras_chave_pergunta:
                for termo in palavras_chave_pergunta:
                    busca_termo = (
                        supabase.table("baseconhecimento")
                        .select("id_conhecimento, conteudo_processado, url_documento, nome_arquivo_origem, palavra_chave, categoria")
                        .ilike("conteudo_processado", f"%{termo}%")
                        .eq("status", "publicado")
                        .limit(10)
                        .execute()
                    )
                    
                    if busca_termo.data:
                        print(f"   [Busca Conteudo] Encontrados {len(busca_termo.data)} resultados para termo '{termo}'")
                        for item in busca_termo.data:
                            id_reg = item.get("id_conhecimento")
                            if id_reg and id_reg not in registros_processados:
                                registros_processados.add(id_reg)
                                conteudo = item.get("conteudo_processado", "")
                                if conteudo:
                                    contextos.append(conteudo)
                                
                                url_doc = item.get("url_documento")
                                if url_doc:
                                    documentos_com_url.append({
                                        "url_documento": url_doc,
                                        "nome_arquivo": item.get("nome_arquivo_origem", "documento"),
                                        "id_conhecimento": id_reg
                                    })
        except Exception as e:
            print(f"   [ERRO Busca Conteudo] {e}")

        # 2.2) Busca em categoria (busca pela pergunta completa E por termos individuais)
        try:
            # Busca pela pergunta completa
            busca_categoria = (
                supabase.table("baseconhecimento")
                .select("id_conhecimento, conteudo_processado, url_documento, nome_arquivo_origem, palavra_chave, categoria")
                .ilike("categoria", f"%{pergunta_lower}%")
                .eq("status", "publicado")
                .limit(10)
                .execute()
            )

            if busca_categoria.data:
                print(f"   [Busca Categoria] Encontrados {len(busca_categoria.data)} resultados em categoria (pergunta completa)")
                for item in busca_categoria.data:
                    id_reg = item.get("id_conhecimento")
                    if id_reg and id_reg not in registros_processados:
                        registros_processados.add(id_reg)
                        conteudo = item.get("conteudo_processado", "")
                        if conteudo:
                            contextos.append(conteudo)
                        
                        url_doc = item.get("url_documento")
                        if url_doc:
                            documentos_com_url.append({
                                "url_documento": url_doc,
                                "nome_arquivo": item.get("nome_arquivo_origem", "documento"),
                                "id_conhecimento": id_reg
                            })
            
            # Busca por termos individuais em categoria
            if palavras_chave_pergunta:
                for termo in palavras_chave_pergunta:
                    busca_cat_termo = (
                        supabase.table("baseconhecimento")
                        .select("id_conhecimento, conteudo_processado, url_documento, nome_arquivo_origem, palavra_chave, categoria")
                        .ilike("categoria", f"%{termo}%")
                        .eq("status", "publicado")
                        .limit(10)
                        .execute()
                    )
                    
                    if busca_cat_termo.data:
                        print(f"   [Busca Categoria] Encontrados {len(busca_cat_termo.data)} resultados para termo '{termo}' em categoria")
                        for item in busca_cat_termo.data:
                            id_reg = item.get("id_conhecimento")
                            if id_reg and id_reg not in registros_processados:
                                registros_processados.add(id_reg)
                                conteudo = item.get("conteudo_processado", "")
                                if conteudo:
                                    contextos.append(conteudo)
                                
                                url_doc = item.get("url_documento")
                                if url_doc:
                                    documentos_com_url.append({
                                        "url_documento": url_doc,
                                        "nome_arquivo": item.get("nome_arquivo_origem", "documento"),
                                        "id_conhecimento": id_reg
                                    })
        except Exception as e:
            print(f"   [ERRO Busca Categoria] {e}")

        # 2.3) Busca em palavra_chave (JSONB) - busca por cada palavra-chave da pergunta
        if palavras_chave_pergunta:
            try:
                # Busca todos os registros publicados e filtra localmente por palavra_chave
                busca_palavras = (
                    supabase.table("baseconhecimento")
                    .select("id_conhecimento, conteudo_processado, url_documento, nome_arquivo_origem, palavra_chave, categoria")
                    .eq("status", "publicado")
                    .limit(50)  # Busca mais registros para filtrar localmente
                    .execute()
                )

                if busca_palavras.data:
                    print(f"   [Busca Palavras] Analisando {len(busca_palavras.data)} registros para palavras-chave")
                    for item in busca_palavras.data:
                        id_reg = item.get("id_conhecimento")
                        if id_reg and id_reg not in registros_processados:
                            # Processa palavra_chave (pode ser JSONB ou string)
                            palavra_chave_data = item.get("palavra_chave")
                            palavra_chave_str = ""
                            
                            if isinstance(palavra_chave_data, list):
                                palavra_chave_str = " ".join([str(p).lower() for p in palavra_chave_data])
                            elif isinstance(palavra_chave_data, str):
                                # Tenta fazer parse se for JSON string
                                try:
                                    import json
                                    parsed = json.loads(palavra_chave_data)
                                    if isinstance(parsed, list):
                                        palavra_chave_str = " ".join([str(p).lower() for p in parsed])
                                    else:
                                        palavra_chave_str = str(palavra_chave_data).lower()
                                except:
                                    palavra_chave_str = str(palavra_chave_data).lower()
                            else:
                                palavra_chave_str = str(palavra_chave_data or "").lower()
                            
                            # Verifica se alguma palavra da pergunta está nas palavras-chave (match exato ou parcial)
                            # Também verifica se alguma palavra-chave está na pergunta
                            match_encontrado = False
                            for palavra in palavras_chave_pergunta:
                                if palavra in palavra_chave_str or any(palavra in str(pk).lower() for pk in (palavra_chave_data if isinstance(palavra_chave_data, list) else [])):
                                    match_encontrado = True
                                    break
                            
                            if match_encontrado:
                                registros_processados.add(id_reg)
                                conteudo = item.get("conteudo_processado", "")
                                if conteudo:
                                    contextos.append(conteudo)
                                
                                url_doc = item.get("url_documento")
                                if url_doc:
                                    documentos_com_url.append({
                                        "url_documento": url_doc,
                                        "nome_arquivo": item.get("nome_arquivo_origem", "documento"),
                                        "id_conhecimento": id_reg
                                    })
            except Exception as e:
                print(f"   [ERRO Busca Palavras] {e}")

    except Exception as e:
        print(f"   [ERRO Busca Geral] Erro ao buscar na base: {e}")
        import traceback
        traceback.print_exc()

    # Remove strings vazias para não poluir o contexto
    contextos_limpos = [c for c in contextos if c]
    print(f"   [Busca] Total de contextos encontrados: {len(contextos_limpos)}")
    print(f"   [Busca] Total de documentos com URL: {len(documentos_com_url)}")
    
    return (contextos_limpos, documentos_com_url)


def _processar_documento_da_url(url_documento: str, pergunta: str) -> str:
    """
    Baixa um documento da URL e processa com Gemini para extrair informação relevante.
    """
    print(f"   [Documento] Processando documento da URL: {url_documento}")
    
    try:
        # Baixa o arquivo temporariamente
        response = requests.get(url_documento, timeout=30)
        response.raise_for_status()
        
        # Determina o tipo MIME baseado na extensão ou Content-Type
        content_type = response.headers.get("Content-Type", "application/pdf")
        if "pdf" in content_type.lower() or url_documento.lower().endswith(".pdf"):
            mime_type = "application/pdf"
        elif "word" in content_type.lower() or url_documento.lower().endswith((".docx", ".doc")):
            mime_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        elif "text" in content_type.lower() or url_documento.lower().endswith(".txt"):
            mime_type = "text/plain"
        else:
            mime_type = "application/octet-stream"
        
        # Salva temporariamente
        with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(url_documento)[1]) as tmp_file:
            tmp_file.write(response.content)
            tmp_path = tmp_file.name
        
        try:
            # Faz upload para o Gemini
            with open(tmp_path, "rb") as f:
                uploaded_file = genai.upload_file(f, mime_type=mime_type)
            
            # Prompt para extrair informação relevante
            prompt = f"""
Você é um assistente acadêmico. Leia o documento fornecido e extraia APENAS as informações relevantes para responder à seguinte pergunta:

PERGUNTA: {pergunta}

INSTRUÇÕES:
- Extraia apenas trechos do documento que sejam diretamente relevantes para a pergunta.
- Se não houver informação relevante no documento, retorne: "Nenhuma informação relevante encontrada neste documento."
- Seja conciso e objetivo.
- Retorne apenas o texto extraído, sem comentários adicionais.
"""
            
            # Processa com Gemini
            response_gemini = gemini_model.generate_content([prompt, uploaded_file])
            resultado = response_gemini.text.strip()
            
            print(f"   [Documento] Informação extraída do documento (primeiros 200 chars): {resultado[:200]}...")
            
            return resultado
            
        finally:
            # Remove arquivo temporário
            try:
                os.unlink(tmp_path)
            except Exception:
                pass
                
    except Exception as e:
        print(f"   [ERRO Documento] Falha ao processar documento: {e}")
        return ""



@router.post("/gerar-resposta")
async def gerar_resposta_com_ia(request: GenerationRequest, current_user: dict = Depends(require_all)):
    """
    Recebe uma pergunta, consulta a base de conhecimento no Supabase de forma abrangente,
    e se não encontrar resposta suficiente, processa documentos das URLs armazenadas.
    """
    print(f"[IA] Processando pergunta: {request.pergunta}")

    # 1) Buscar contexto na base de conhecimento (busca abrangente)
    contextos, documentos_com_url = _buscar_contextos_da_base(request.pergunta)
    contexto_base = "\n\n---\n\n".join(contextos[:10]) if contextos else ""
    
    print(f"[IA] Contextos encontrados na base: {len(contextos)}")
    print(f"[IA] Documentos com URL disponíveis: {len(documentos_com_url)}")

    # 2) Se não encontrou contexto suficiente, processa documentos das URLs
    contexto_documentos = ""
    if not contexto_base or len(contextos) < 2:
        print("[IA] Contexto insuficiente. Processando documentos das URLs...")
        for doc in documentos_com_url[:3]:  # Limita a 3 documentos para não sobrecarregar
            try:
                resultado_doc = _processar_documento_da_url(doc["url_documento"], request.pergunta)
                if resultado_doc and "Nenhuma informação relevante" not in resultado_doc:
                    contexto_documentos += f"\n\n--- Documento: {doc['nome_arquivo']} ---\n{resultado_doc}\n"
            except Exception as e:
                print(f"   [ERRO] Falha ao processar documento {doc['url_documento']}: {e}")
                continue

    # 3) Combinar todos os contextos
    partes_contexto: list[str] = []
    if request.contexto:
        partes_contexto.append(str(request.contexto))
    if contexto_base:
        partes_contexto.append(contexto_base)
    if contexto_documentos:
        partes_contexto.append(contexto_documentos)

    contexto_final = (
        "\n\n---\n\n".join(partes_contexto)
        if partes_contexto
        else "NENHUM CONTEXTO DISPONÍVEL."
    )

    # 4) Montar o prompt para o Gemini
    prompt = f"""
Você é um assistente acadêmico. Sua tarefa é responder à pergunta do usuário de forma clara, objetiva e pedagógica.
Baseie-se EXCLUSIVAMENTE no contexto fornecido abaixo (que vem da base de conhecimento do sistema e documentos processados).
Não use nenhum conhecimento externo ou invente informações.
Se a resposta não estiver claramente presentes no contexto, diga exatamente:
"Com base no material que tenho, não encontrei uma resposta para sua pergunta.".

================ CONTEXTO =================
{contexto_final}
===========================================

Pergunta do usuário: {request.pergunta}

Responda de forma concisa e bem estruturada:
"""

    try:
        response = gemini_model.generate_content(prompt)
        return {"resposta": response.text}
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao comunicar com a API do Gemini: {e}",
        )

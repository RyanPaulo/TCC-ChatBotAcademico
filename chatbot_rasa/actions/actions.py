import platform
import asyncio
from typing import Any, Text, Dict, List, Optional
from datetime import datetime, timedelta
from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
import requests
from rasa_sdk.events import SlotSet, ActiveLoop
import logging
import json
import re
import random
from urllib.parse import quote, unquote
import unicodedata
import jwt
import threading
import time

if platform.system() == "Windows":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

API_URL = "http://localhost:8000"


### CONFIGURAÇÃO DE LOGGING ###
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('rasa_bot.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

### VERIFICAÇÃO DE TOKEN DE AUTENTICAÇÃO ###
### FUNÇÃO PARA VERIFICAR SE O TOKEN DE AUTENTICAÇÃO É VÁLIDO ###
def verificar_token_valido(access_token: str) -> bool:
    """
    Verifica se o token de autenticação ainda é válido.
    
    Args:
        access_token: Token JWT a ser verificado
    
    Returns:
        True se o token é válido, False caso contrário
    """
    if not access_token:
        return False
    
    try:
        # Tentar decodificar o token JWT para verificar se está expirado
        # Não precisamos verificar a assinatura, apenas a expiração
        decoded = jwt.decode(access_token, options={"verify_signature": False})
        
        # Verificar se o token tem campo 'exp' (expiração)
        if 'exp' in decoded:
            exp_time = decoded['exp']
            current_time = datetime.now().timestamp()
            
            # Verificar se o token expirou (com margem de 60 segundos)
            if current_time >= (exp_time - 60):
                logger.warning(f"Token expirado ou expirando em breve. Exp: {exp_time}, Atual: {current_time}")
                return False
        
        return True
    except jwt.ExpiredSignatureError:
        logger.warning("Token JWT expirado")
        return False
    except jwt.InvalidTokenError as e:
        logger.warning(f"Token JWT invalido: {e}")
        return False
    except Exception as e:
        logger.warning(f"Erro ao verificar token: {e}")
        # Em caso de erro, assumir que o token pode ser válido (não bloquear)
        return True

### FUNÇÃO PARA OBTER HEADERS DE AUTENTICAÇÃO ###
def get_auth_headers(tracker: Tracker, verificar_validade: bool = True) -> dict:
    """
    Retorna headers HTTP com token de autenticação se disponível e válido.
    
    Args:
        tracker: Tracker do Rasa
        verificar_validade: Se True, verifica se o token ainda é válido antes de usar
    
    Returns:
        Dicionário com headers HTTP, incluindo Authorization se token válido
    """
    access_token = tracker.get_slot("access_token")
    autenticado = tracker.get_slot("autenticado")
    headers = {"Content-Type": "application/json"}
    
    if access_token:
        # Verificar se o token ainda é válido
        if verificar_validade:
            if not verificar_token_valido(access_token):
                logger.warning("Token de autenticacao invalido ou expirado. Requisicao sera feita sem autenticacao.")
                # Limpar slots de autenticação se token inválido
                return headers
        
        headers["Authorization"] = f"Bearer {access_token}"
        logger.info(f"Token de autenticacao incluido nos headers (primeiros 20 chars: {access_token[:20]}...)")
    else:
        if autenticado:
            logger.warning("Usuario marcado como autenticado mas token nao encontrado. Possivel problema na sessao.")
        else:
            logger.debug("Token de autenticacao NAO encontrado no tracker. Requisicao sera feita sem autenticacao.")
    
    return headers

### FUNÇÃO PARA VERIFICAR E ATUALIZAR INATIVIDADE ###
def verificar_e_atualizar_inatividade(tracker: Tracker, dispatcher: CollectingDispatcher) -> tuple[bool, List[Dict[Text, Any]]]:
    """
    Verifica inatividade e atualiza timestamp se usuário estiver ativo.
    Retorna (ainda_autenticado, eventos) onde eventos podem incluir deslogar se inativo.
    
    Args:
        tracker: Tracker do Rasa
        dispatcher: Dispatcher para enviar mensagens
    
    Returns:
        Tupla (ainda_autenticado, eventos) onde:
        - ainda_autenticado: True se ainda autenticado após verificação
        - eventos: Lista de eventos (pode incluir deslogar se inativo)
    """
    autenticado = tracker.get_slot("autenticado")
    access_token = tracker.get_slot("access_token")
    ultima_atividade_str = tracker.get_slot("ultima_atividade_timestamp")
    
    # Se não estiver autenticado, não precisa verificar inatividade
    if not autenticado or not access_token:
        return (False, [])
    
    # Se não houver timestamp, considerar como primeira interação e salvar timestamp atual
    if not ultima_atividade_str:
        timestamp_atual = datetime.now().isoformat()
        logger.info(f"[VerificarInatividade] Primeira interacao apos autenticacao. Salvando timestamp.")
        return (True, [SlotSet("ultima_atividade_timestamp", timestamp_atual)])
    
    # Verificar se passou mais de 2 minutos (120 segundos)
    try:
        ultima_atividade = datetime.fromisoformat(ultima_atividade_str)
        tempo_decorrido = (datetime.now() - ultima_atividade).total_seconds()
        timeout_minutos = 10
        timeout_segundos = timeout_minutos * 60
        
        if tempo_decorrido > timeout_segundos:
            # Usuário inativo há mais de 2 minutos - deslogar
            logger.info(f"[VerificarInatividade] Usuario inativo por {tempo_decorrido/60:.1f} minutos. Deslogando automaticamente.")
            dispatcher.utter_message(text="Voce ficou inativo por mais de 10 minutos. Por seguranca, sua sessao foi encerrada. Por favor, faca login novamente.")
            
            # Limpar todos os slots de autenticação
            eventos = [
                SlotSet("autenticado", False),
                SlotSet("access_token", None),
                SlotSet("ultima_atividade_timestamp", None),
                SlotSet("email_institucional", None),
                SlotSet("matricula_ra", None),
                SlotSet("tipo_pergunta_ra", None),
                SlotSet("parametro_pergunta_ra", None),
                ActiveLoop("form_autenticacao")
            ]
            return (False, eventos)
        else:
            # Usuário ainda ativo - atualizar timestamp
            tempo_restante = timeout_segundos - tempo_decorrido
            logger.debug(f"[VerificarInatividade] Usuario ativo. Tempo restante: {tempo_restante/60:.1f} minutos.")
            timestamp_atual = datetime.now().isoformat()
            return (True, [SlotSet("ultima_atividade_timestamp", timestamp_atual)])
            
    except (ValueError, TypeError) as e:
        # Se houver erro ao processar timestamp, resetar
        logger.warning(f"[VerificarInatividade] Erro ao processar timestamp: {e}. Resetando timestamp.")
        timestamp_atual = datetime.now().isoformat()
        return (True, [SlotSet("ultima_atividade_timestamp", timestamp_atual)])

### FUNÇÃO PARA VERIFICAR AUTENTICAÇÃO COMPLETA ###
def verificar_autenticacao_completa(tracker: Tracker) -> tuple[bool, Optional[str]]:
    """
    Verifica se o usuário está completamente autenticado e o token é válido.
    
    Args:
        tracker: Tracker do Rasa
    
    Returns:
        Tupla (autenticado, access_token) onde:
        - autenticado: True se usuário está autenticado e token válido
        - access_token: Token se válido, None caso contrário
    """
    autenticado = tracker.get_slot("autenticado")
    access_token = tracker.get_slot("access_token")
    
    if not autenticado or not access_token:
        return (False, None)
    
    # Verificar se o token ainda é válido
    if not verificar_token_valido(access_token):
        logger.warning("Token de autenticacao invalido ou expirado. Usuario precisa reautenticar.")
        return (False, None)
    
    return (True, access_token)

### FUNÇÃO PARA ATUALIZAR TIMESTAMP DA ÚLTIMA ATIVIDADE ###
def atualizar_timestamp_atividade() -> List[Dict[Text, Any]]:
    """
    Helper para atualizar o timestamp da última atividade do usuário.
    Retorna uma lista com o evento SlotSet para atualizar o timestamp.
    """
    timestamp_atual = datetime.now().isoformat()
    return [SlotSet("ultima_atividade_timestamp", timestamp_atual)]


### HELPER PARA DELETAR MENSAGENS DO TELEGRAM ###
TELEGRAM_BOT_TOKEN = "8309691579:AAED-SjbFO6WcjOO75muLKt-_kaPwnTSyog"  # Do credentials.yml
TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"

# Dicionário global para rastrear threads de "digitando..." ativas
_threads_digitando = {}
_lock_threads = threading.Lock()

### FUNÇÃO PARA ENVIAR INDICADOR DE DIGITANDO ###
def enviar_indicador_digitando(chat_id: str) -> bool:
    """
    Envia o indicador de "digitando..." no Telegram.
    
    Args:
        cha(obtt_id: ID do chat ido do tracker)
    
    Returns:
        True se enviado com sucesso, False caso contrário
    """
    if not chat_id:
        return False
    
    try:
        response = requests.post(
            f"{TELEGRAM_API_URL}/sendChatAction",
            json={
                "chat_id": chat_id,
                "action": "typing"  # Mostra "digitando..."
            },
            timeout=5
        )
        response.raise_for_status()
        return True
    except Exception as e:
        logger.debug(f"Erro ao enviar indicador de digitando: {e}")
        return False

### FUNÇÃO PARA MANTER INDICADOR DE DIGITANDO ATIVO ###
def manter_indicador_digitando(chat_id: str, duracao: int = 30) -> threading.Thread:
    """
    Mantém o indicador de digitando ativo por um período.
    O Telegram limita o indicador a 5 segundos, então precisamos reenviar.
    
    Args:
        chat_id: ID do chat
        duracao: Duração em segundos para manter o indicador ativo
    
    Returns:
        Thread que está mantendo o indicador ativo (para poder parar depois)
    """
    if not chat_id:
        return None
    
    # Parar qualquer thread anterior para este chat_id
    parar_indicador_digitando(chat_id)
    
    # Flag para controlar quando parar
    parar_flag = threading.Event()
    
    def enviar_periodicamente():
        start_time = time.time()
        while not parar_flag.is_set() and (time.time() - start_time < duracao):
            enviar_indicador_digitando(chat_id)
            # Aguardar 4 segundos ou até receber sinal para parar
            if parar_flag.wait(timeout=4):
                break
    
    # Executar em thread separada para não bloquear
    thread = threading.Thread(target=enviar_periodicamente, daemon=True)
    thread.start()
    
    # Armazenar thread e flag no dicionário global
    with _lock_threads:
        _threads_digitando[chat_id] = {
            'thread': thread,
            'flag': parar_flag
        }
    
    return thread

### FUNÇÃO PARA PARAR INDICADOR DE DIGITANDO ###
def parar_indicador_digitando(chat_id: str) -> bool:
    """
    Para o indicador de "digitando..." para um chat específico.
    
    Args:
        chat_id: ID do chat
    
    Returns:
        True se parou com sucesso, False caso contrário
    """
    if not chat_id:
        return False
    
    with _lock_threads:
        if chat_id in _threads_digitando:
            thread_info = _threads_digitando[chat_id]
            # Sinalizar para parar
            thread_info['flag'].set()
            # Remover do dicionário
            del _threads_digitando[chat_id]
            logger.debug(f"Indicador de digitando parado para chat_id: {chat_id}")
            return True
    
    return False

### FUNÇÃO PARA INICIAR INDICADOR DE DIGITANDO EM UMA ACTION ###
def iniciar_indicador_em_action(tracker: Tracker, duracao: int = 20) -> Optional[str]:
    """
    Inicia o indicador de "digitando..." para uma action.
    Retorna o chat_id para uso posterior.
    
    Args:
        tracker: Tracker do Rasa
        duracao: Duração em segundos para manter o indicador (padrão: 20)
    
    Returns:
        chat_id como string ou None
    """
    chat_id = obter_chat_id_do_tracker(tracker)
    if chat_id:
        manter_indicador_digitando(chat_id, duracao=duracao)
    return chat_id

### FUNÇÃO PARA PARAR INDICADOR DE DIGITANDO ANTES DE ENVIAR A RESPOSTA FINAL ###
def parar_indicador_antes_de_resposta(chat_id: Optional[str]) -> None:
    """
    Para o indicador de "digitando..." antes de enviar a resposta final.
    Deve ser chamado antes de cada dispatcher.utter_message que envia a resposta final.
    
    Args:
        chat_id: ID do chat (pode ser None)
    """
    if chat_id:
        parar_indicador_digitando(chat_id)
        # Pequeno delay para garantir que o Telegram processe o comando de parar
        time.sleep(0.1)

### FUNÇÃO PARA DELETAR MENSAGEM DO TELEGRAM ###
def deletar_mensagem_telegram(chat_id: str, message_id: int) -> bool:
    """
    Deleta uma mensagem do Telegram usando a Bot API.
    
    Args:
        chat_id: ID do chat (obtido do tracker)
        message_id: ID da mensagem a ser deletada
        
    Returns:
        True se a mensagem foi deletada com sucesso, False caso contrário
        
    Nota: Mensagens só podem ser deletadas em até 48 horas após o envio.
    """
    try:
        url = f"{TELEGRAM_API_URL}/deleteMessage"
        payload = {
            "chat_id": chat_id,
            "message_id": message_id
        }
        
        response = requests.post(url, json=payload, timeout=5)
        response.raise_for_status()
        
        result = response.json()
        if result.get("ok", False):
            logger.info(f"[Telegram] Mensagem {message_id} deletada com sucesso do chat {chat_id}")
            return True
        else:
            logger.warning(f"[Telegram] Erro ao deletar mensagem: {result.get('description', 'Erro desconhecido')}")
            return False
            
    except requests.exceptions.RequestException as e:
        logger.error(f"[Telegram] Erro de rede ao deletar mensagem: {e}")
        return False
    except Exception as e:
        logger.error(f"[Telegram] Erro ao deletar mensagem do Telegram: {e}")
        return False

### FUNÇÃO PARA OBTER CHAT ID DO TRACKER ###
def obter_chat_id_do_tracker(tracker: Tracker) -> Optional[str]:
    """
    Extrai o chat_id do tracker (para Telegram).
    
    Args:
        tracker: Tracker do Rasa
        
    Returns:
        chat_id como string ou None se não encontrado
    """
    # O sender_id geralmente contém o chat_id para Telegram
    sender_id = tracker.sender_id
    
    if sender_id:
        return str(sender_id)
    
    # Tentar obter do metadata se disponível
    metadata = tracker.latest_message.get('metadata', {})
    if metadata:
        chat_id = metadata.get('chat_id') or metadata.get('chat', {}).get('id')
        if chat_id:
            return str(chat_id)
    
    # Tentar obter de eventos recentes
    try:
        events = tracker.events
        for event in reversed(events[-10:]):  # Verificar últimos 10 eventos
            if isinstance(event, dict):
                event_metadata = event.get('metadata', {})
                if event_metadata:
                    chat_id = event_metadata.get('chat_id') or event_metadata.get('chat', {}).get('id')
                    if chat_id:
                        return str(chat_id)
    except Exception as e:
        logger.debug(f"Erro ao buscar chat_id em eventos: {e}")
    
    return None

### CACHE HELPER ###
### CLASSE PARA CACHE DE REQUISIÇÕES FREQUENTES ###
class CacheHelper:
    """
    Cache de requisições frequentes para melhorar performance
    """
    _cache_disciplinas = {}
    _cache_professores = {}
    _cache_coordenadores = {}
    _cache_timestamp = {}
    CACHE_TTL = 300  # 5 minutos
    
    ### FUNÇÃO PARA NORMALIZAR NOME DA DISCIPLINA ###
    @staticmethod
    def _normalizar_nome_disciplina(nome: str) -> str:
        """
        Normaliza o nome da disciplina para busca:
        - Remove espaços extras
        - Remove acentos
        - Converte para minúsculas
        """
        # Remove espaços extras e converte para minúsculas
        nome = ' '.join(nome.strip().split())
        # Remove acentos
        nome_normalizado = unicodedata.normalize('NFD', nome)
        nome_normalizado = ''.join(char for char in nome_normalizado if unicodedata.category(char) != 'Mn')
        return nome_normalizado.lower()
    
    ### FUNÇÃO PARA BUSCAR ID DA DISCIPLINA ###
    @staticmethod
    def get_disciplina_id(disciplina_nome: str, headers: dict = None) -> str | None:
        """
        Busca ID de disciplina com cache.
        Primeiro tenta buscar na lista de disciplinas (método mais confiável).
        Se não encontrar, tenta endpoint de cronograma como fallback.
        
        Args:
            disciplina_nome: Nome da disciplina a buscar
            headers: Headers HTTP opcionais (incluindo autenticação)
        """
        # Normalizar nome (limpar espaços extras)
        nome_original = disciplina_nome.strip()
        nome_busca = ' '.join(nome_original.split())  # Remove espaços múltiplos
        
        # Verificar cache
        if nome_busca in CacheHelper._cache_disciplinas:
            timestamp = CacheHelper._cache_timestamp.get(f"disc_{nome_busca}")
            if timestamp and datetime.now() - timestamp < timedelta(seconds=CacheHelper.CACHE_TTL):
                logger.info(f"Cache HIT: disciplina '{nome_busca}'")
                return CacheHelper._cache_disciplinas[nome_busca]
        
        # Se não tiver headers, criar headers básicos
        if headers is None:
            headers = {"Content-Type": "application/json"}
        
        # PRIMEIRO: Tentar buscar na lista de disciplinas (método mais confiável)
        logger.info(f"Cache MISS: buscando disciplina '{nome_busca}' na lista de disciplinas")
        id_disciplina = CacheHelper._buscar_disciplina_na_lista(nome_busca, headers)
        
        if id_disciplina:
            return id_disciplina
        
        # FALLBACK: Tentar buscar via endpoint de cronograma
        try:
            logger.info(f"Tentando buscar disciplina '{nome_busca}' via endpoint de cronograma")
            
            # CORREÇÃO: Codificar o nome na URL corretamente
            nome_codificado = quote(nome_busca, safe='')
            url = f"{API_URL}/disciplinas/get_diciplina_nome/{nome_codificado}/cronograma"
            logger.debug(f"URL da busca: {url}")
            
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.ok:
                cronogramas = response.json()
                if cronogramas and isinstance(cronogramas, list) and len(cronogramas) > 0:
                    id_disciplina = cronogramas[0].get('id_disciplina')
                    if id_disciplina:
                        CacheHelper._cache_disciplinas[nome_busca] = id_disciplina
                        CacheHelper._cache_timestamp[f"disc_{nome_busca}"] = datetime.now()
                        logger.info(f"Cache SET: disciplina '{nome_busca}' -> {id_disciplina} (via cronograma)")
                        return id_disciplina
            
            return None
        except requests.exceptions.RequestException as e:
            logger.error(f"Erro ao buscar disciplina via cronograma '{nome_busca}': {e}")
            return None
    
    ### FUNÇÃO PARA BUSCAR DISCIPLINA NA LISTA COMPLETA ###
    @staticmethod
    def _buscar_disciplina_na_lista(nome_busca: str, headers: dict = None) -> str | None:
        """
        Busca disciplina na lista completa de disciplinas fazendo match parcial.
        Fallback quando o endpoint de cronograma não encontra.
        
        Args:
            nome_busca: Nome da disciplina a buscar
            headers: Headers HTTP opcionais (incluindo autenticação)
        """
        try:
            # Se não tiver headers, criar headers básicos
            if headers is None:
                headers = {"Content-Type": "application/json"}
            
            # Buscar lista de todas as disciplinas
            response = requests.get(f"{API_URL}/disciplinas/lista_disciplina/", headers=headers, timeout=10)
            if not response.ok:
                return None
            
            disciplinas = response.json()
            if not disciplinas or not isinstance(disciplinas, list):
                return None
            
            nome_busca_normalizado = CacheHelper._normalizar_nome_disciplina(nome_busca)
            
            # Extrair palavras-chave do nome buscado (palavras com mais de 2 caracteres)
            palavras_chave_busca = [p for p in nome_busca_normalizado.split() if len(p) > 2]
            
            melhor_match = None
            melhor_score = 0
            
            # Fazer match parcial
            for disc in disciplinas:
                if not isinstance(disc, dict):
                    continue
                
                nome_disc = disc.get('nome_disciplina', '')
                if not nome_disc:
                    continue
                
                nome_disc_normalizado = CacheHelper._normalizar_nome_disciplina(nome_disc)
                
                # Verificar match exato ou parcial
                score = 0
                
                # Match exato (maior prioridade)
                if nome_busca_normalizado == nome_disc_normalizado:
                    score = 100
                # Nome buscado está contido no nome da disciplina (ex: "Sistemas Distribuídos" em "Desenvolvimento de Sistemas Distribuídos")
                elif nome_busca_normalizado in nome_disc_normalizado:
                    score = 80
                # Nome da disciplina está contido no nome buscado
                elif nome_disc_normalizado in nome_busca_normalizado:
                    score = 70
                # Match por palavras-chave (verificar se todas as palavras importantes estão presentes)
                elif palavras_chave_busca:
                    palavras_disc = set(nome_disc_normalizado.split())
                    palavras_match = sum(1 for p in palavras_chave_busca if p in nome_disc_normalizado)
                    if palavras_match == len(palavras_chave_busca):
                        score = 60 + palavras_match * 5
                    elif palavras_match > 0:
                        score = 30 + palavras_match * 5
                
                if score > melhor_score:
                    melhor_score = score
                    melhor_match = disc
            
            if melhor_match and melhor_score >= 30:
                id_disciplina = melhor_match.get('id_disciplina')
                nome_disc_encontrado = melhor_match.get('nome_disciplina', '')
                if id_disciplina:
                    # Armazenar no cache com o nome original buscado
                    CacheHelper._cache_disciplinas[nome_busca] = id_disciplina
                    CacheHelper._cache_timestamp[f"disc_{nome_busca}"] = datetime.now()
                    logger.info(f"Disciplina encontrada na lista: '{nome_busca}' -> '{nome_disc_encontrado}' ({id_disciplina}) [score: {melhor_score}]")
                    return id_disciplina
            
            logger.warning(f"Disciplina '{nome_busca}' nao encontrada na lista de disciplinas (melhor score: {melhor_score})")
            return None
            
        except Exception as e:
            logger.error(f"Erro ao buscar disciplina na lista: {e}")
            return None
    
    ### FUNÇÃO PARA BUSCAR LISTA DE PROFESSORES ###
    @staticmethod
    def get_lista_professores() -> list:
        """Busca lista de professores com cache"""
        cache_key = "professores"
        timestamp = CacheHelper._cache_timestamp.get(cache_key)
        
        if cache_key in CacheHelper._cache_professores:
            if timestamp and datetime.now() - timestamp < timedelta(seconds=CacheHelper.CACHE_TTL):
                logger.info("Cache HIT: lista de professores")
                return CacheHelper._cache_professores[cache_key]
        
        try:
            logger.info("Cache MISS: buscando lista de professores na API")
            response = requests.get(f"{API_URL}/professores/lista_professores/", timeout=10)
            response.raise_for_status()
            professores = response.json()
            
            CacheHelper._cache_professores[cache_key] = professores
            CacheHelper._cache_timestamp[cache_key] = datetime.now()
            logger.info(f"Cache SET: {len(professores)} professores")
            
            return professores
        except requests.exceptions.RequestException as e:
            logger.error(f"Erro ao buscar professores: {e}")
            return []
    
    ### FUNÇÃO PARA BUSCAR LISTA DE COORDENADORES ###
    @staticmethod
    def get_lista_coordenadores() -> list:
        """Busca lista de coordenadores com cache"""
        cache_key = "coordenadores"
        timestamp = CacheHelper._cache_timestamp.get(cache_key)
        
        if cache_key in CacheHelper._cache_coordenadores:
            if timestamp and datetime.now() - timestamp < timedelta(seconds=CacheHelper.CACHE_TTL):
                logger.info("Cache HIT: lista de coordenadores")
                return CacheHelper._cache_coordenadores[cache_key]
        
        try:
            logger.info("Cache MISS: buscando lista de coordenadores na API")
            response = requests.get(f"{API_URL}/coordenador/get_list_coordenador/", timeout=10)
            response.raise_for_status()
            coordenadores = response.json()
            
            CacheHelper._cache_coordenadores[cache_key] = coordenadores
            CacheHelper._cache_timestamp[cache_key] = datetime.now()
            logger.info(f"Cache SET: {len(coordenadores)} coordenadores")
            
            return coordenadores
        except requests.exceptions.RequestException as e:
            logger.error(f"Erro ao buscar coordenadores: {e}")
            return []
    
    ### FUNÇÃO PARA LIMPAR CACHE ###
    @staticmethod
    def clear_cache():
        """Limpa o cache (útil para testes ou atualizações)"""
        CacheHelper._cache_disciplinas.clear()
        CacheHelper._cache_professores.clear()
        CacheHelper._cache_coordenadores.clear()
        CacheHelper._cache_timestamp.clear()
        logger.info("Cache limpo")


### ERROR HANDLER ###
### CLASSE PARA TRATAR ERROS DE API DE FORMA AMIGÁVEL E REGISTRAR LOGS ###
class ErrorHandler:
    """
    Trata erros de API de forma amigável e registra logs
    """
    
    # Mensagens variadas para erros 500 (Internal Server Error)
    _MENSAGENS_ERRO_500 = [
        "Ocorreu um erro ao processar sua solicitacao. Tente novamente mais tarde.",
        "Ocorreu um erro no nosso servidor interno. Tente novamente mais tarde.",
        "Nossa equipe foi notificada sobre o problema. Por favor, tente novamente mais tarde.",
        "Ocorreu um erro temporario no servidor. Tente novamente em alguns instantes.",
        "Desculpe, estamos com problemas tecnicos. Tente novamente mais tarde.",
        "Ocorreu um erro interno. Nossa equipe foi notificada. Tente novamente mais tarde.",
        "Nao foi possivel processar sua solicitacao no momento. Tente novamente mais tarde.",
        "O servidor encontrou um erro inesperado. Tente novamente mais tarde."
    ]
    
    ### FUNÇÃO PARA OBTER MENSAGEM ALEATÓRIA PARA ERROS 500 ###
    @staticmethod
    def get_mensagem_erro_500() -> str:
        """
        Retorna uma mensagem aleatória para erros 500 (Internal Server Error).
        Útil para casos onde o tratamento de erro é manual.
        """
        return random.choice(ErrorHandler._MENSAGENS_ERRO_500)
    
    ### FUNÇÃO PARA TRATAR ERROS DE API DE FORMA AMIGÁVEL ###
    @staticmethod
    def handle_api_error(dispatcher: CollectingDispatcher, error: Exception, 
                        context: str = "", action_name: str = ""):
        """Trata erros de API de forma amigável"""
        error_type = type(error).__name__
        error_msg = str(error)
        
        # Log estruturado
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "action": action_name,
            "context": context,
            "error_type": error_type,
            "error_message": error_msg
        }
        logger.error(f"API_ERROR: {json.dumps(log_entry, ensure_ascii=False)}")
        
        # Mensagens específicas por tipo de erro
        if isinstance(error, requests.exceptions.Timeout):
            dispatcher.utter_message(
                text="O servidor esta demorando para responder. Por favor, tente novamente em alguns instantes."
            )
        elif isinstance(error, requests.exceptions.ConnectionError):
            dispatcher.utter_message(
                text="Nao foi possivel conectar ao servidor. Verifique sua conexao ou tente mais tarde."
            )
        elif isinstance(error, requests.exceptions.HTTPError):
            if hasattr(error, 'response') and error.response:
                status_code = error.response.status_code
                if status_code == 404:
                    dispatcher.utter_message(
                        text="A informacao solicitada nao foi encontrada no sistema."
                    )
                elif status_code == 500:
                    # Selecionar mensagem aleatória para erro 500
                    mensagem_erro = random.choice(ErrorHandler._MENSAGENS_ERRO_500)
                    dispatcher.utter_message(text=mensagem_erro)
                elif status_code == 503:
                    dispatcher.utter_message(
                        text="O servico esta temporariamente indisponivel. Tente novamente em alguns minutos."
                    )
                else:
                    dispatcher.utter_message(
                        text=f"Ocorreu um erro ao processar sua solicitacao (codigo {status_code}). Tente novamente."
                    )
            else:
                dispatcher.utter_message(
                    text="Ocorreu um erro ao processar sua solicitacao. Tente novamente."
                )
        elif isinstance(error, requests.exceptions.JSONDecodeError):
            dispatcher.utter_message(
                text="O servidor retornou uma resposta invalida. Tente novamente mais tarde."
            )
        else:
            dispatcher.utter_message(
                text="Desculpe, ocorreu um erro inesperado. Por favor, tente novamente."
            )


### RESPONSE VALIDATOR ###
### CLASSE PARA VALIDAR RESPOSTAS DA API ANTES DE USAR ###
class ResponseValidator:
    """
    Valida respostas da API antes de usar
    
    Args:
        response: Resposta da API
        expected_keys: Chaves esperadas na resposta
    """
    
    ### FUNÇÃO PARA VALIDAR RESPOSTA JSON DA API ###
    @staticmethod
    def validate_json_response(response: requests.Response, 
                              expected_keys: List[str] = None) -> Optional[Dict]:
        """Valida se a resposta é JSON válido e tem as chaves esperadas"""
        try:
            data = response.json()
            
            if expected_keys:
                missing_keys = [key for key in expected_keys if key not in data]
                if missing_keys:
                    logger.warning(f"Resposta da API sem chaves esperadas: {missing_keys}")
                    return None
            
            return data
        except json.JSONDecodeError as e:
            logger.error(f"Resposta da API nao e JSON valido: {e}")
            return None
    ### FUNÇÃO PARA VALIDAR RESPOSTA DE LISTA ###
    @staticmethod
    def validate_list_response(response: requests.Response) -> List:
        """
        Valida se a resposta é uma lista válida.
        Suporta diferentes formatos de resposta da API.
        """
        try:
            data = response.json()
            
            if isinstance(data, list):
                return data
            elif isinstance(data, dict) and 'value' in data:
                # Algumas APIs retornam {"value": [...]}
                return data['value']
            else:
                logger.warning(f"Resposta nao e uma lista: {type(data)}")
                return []
        except json.JSONDecodeError as e:
            logger.error(f"Resposta da API nao e JSON valido: {e}")
            return []

### FUNÇÃO PARA SALVAR PERGUNTA DO ALUNO ###
def salvar_pergunta_aluno(pergunta: str, topico: list[str] = None, tracker: Tracker = None, headers: dict = None) -> bool:
    """
    Salva a pergunta do aluno no endpoint de mensagens.
    Extrai tópicos automaticamente da pergunta.
    
    Args:
        pergunta: Texto da pergunta do aluno
        topico: Lista de tópicos (opcional, será extraído se não fornecido)
        tracker: Tracker opcional para obter headers de autenticação
        headers: Headers HTTP opcionais (se não fornecido e tracker disponível, será obtido do tracker)
    """
    try:
        # Se não tiver headers mas tiver tracker, obter headers do tracker
        if headers is None and tracker:
            headers = get_auth_headers(tracker, verificar_validade=True)
        
        # Se ainda não tiver headers, criar headers básicos
        if headers is None:
            headers = {"Content-Type": "application/json"}
        
        # Extrair tópicos básicos da pergunta (pode melhorar com NLP)
        if not topico:
            topico = extrair_topicos_da_pergunta(pergunta, headers)
        
        payload = {
            "primeira_pergunta": pergunta,
            "topico": topico,
            "feedback": "",  # Vazio inicialmente
            "data_hora": datetime.now().isoformat()
        }
        
        response = requests.post(
            f"{API_URL}/mensagens_aluno/",
            json=payload,
            headers=headers,
            timeout=10
        )
        response.raise_for_status()
        return True
    except Exception as e:
        # CORREÇÃO: Usar logger ao invés de print para consistência
        logger.error(f"Erro ao salvar pergunta: {e}")
        return False

### FUNÇÃO PARA EXTRAIR TÓPICOS DA PERGUNTA ###
def extrair_topicos_da_pergunta(pergunta: str, headers: dict = None) -> list[str]:
    """
    Extrai tópicos da pergunta.
    Primeiro tenta classificar como Institucional, depois verifica se é de Conteúdo.
    
    Args:
        pergunta: Texto da pergunta
        headers: Headers HTTP opcionais (incluindo autenticação)
    """
    topicos = []
    pergunta_lower = pergunta.lower()
    
    # 1. Verificar se é dúvida institucional
    topicos_institucionais = {
        "tcc": "TCC",
        "trabalho de conclusão": "TCC",
        "aps": "APS",
        "atividade prática": "APS",
        "estágio": "Estágio",
        "estagio": "Estágio",
        "horas complementares": "Horas Complementares",
        "professor": "Docente",
        "docente": "Docente",
        "aviso": "Aviso",
        "comunicado": "Aviso",
        "disciplina": "Disciplina",
        "matéria": "Disciplina",
        "aula": "Disciplina"
    }
    
    for palavra_chave, topico in topicos_institucionais.items():
        if palavra_chave in pergunta_lower:
            topicos.append(topico)
    
    # 2. Se não encontrou tópico institucional, verificar se é dúvida de conteúdo
    # Buscar na base de conhecimento para ver se há palavras-chave correspondentes
    if not topicos:
        try:
            # Se não tiver headers, criar headers básicos
            if headers is None:
                headers = {"Content-Type": "application/json"}
            
            response = requests.get(
                f"{API_URL}/baseconhecimento/get_buscar",
                params={"q": pergunta},
                headers=headers,
                timeout=10
            )
            if response.ok:
                dados = response.json()
                contextos = dados.get("contextos", [])
                if contextos and len(contextos) > 0:
                    # É dúvida de conteúdo - adicionar marcador
                    topicos.append("Conteúdo")
        except Exception as e:
            logger.debug(f"Erro ao verificar conteudo na base de conhecimento: {e}")
            # Pass silencioso - se falhar, continua sem adicionar tópico de conteúdo
    
    # Retornar tópicos encontrados ou "Geral" como padrão
    return topicos if topicos else ["Geral"]

### FUNÇÃO HELPER PARA BUSCAR ID DE DISCIPLINA POR NOME ###
def get_disciplina_id_by_name(disciplina_nome: Text, tracker: Tracker = None) -> str | None:
    """
    Busca ID de disciplina usando cache.
    NOTA: Usa endpoint de cronograma que aceita nome (solução temporária).
    
    Args:
        disciplina_nome: Nome da disciplina a buscar
        tracker: Tracker opcional para obter headers de autenticação
    """
    headers = None
    if tracker:
        headers = get_auth_headers(tracker, verificar_validade=True)
    
    return CacheHelper.get_disciplina_id(disciplina_nome, headers)

### FUNÇÃO PARA BUSCAR URLs DE DOCUMENTOS RELACIONADOS ###
def buscar_urls_documentos_relacionados(termo_busca: str, limite: int = 3, headers: dict = None) -> list[str]:
    """
    Busca URLs de documentos relacionados a um termo usando endpoints existentes da API.
    Usa /baseconhecimento/get_baseconhecimento_url_documento/{termo} para buscar documentos.
    
    Args:
        termo_busca: Termo para buscar documentos
        limite: Número máximo de URLs para retornar
        headers: Headers HTTP opcionais (incluindo autenticação)
        
    Returns:
        Lista de URLs de documentos encontrados
    """
    urls_encontradas = []
    
    # Se não foram fornecidos headers, usar apenas Content-Type
    if headers is None:
        headers = {"Content-Type": "application/json"}
    
    try:
        # Extrair palavras-chave do termo de busca (palavras com mais de 3 caracteres)
        palavras_chave = re.findall(r'\b\w{4,}\b', termo_busca.lower())
        
        # Se não houver palavras-chave, usar o termo completo
        if not palavras_chave:
            palavras_chave = [termo_busca[:50]]  # Limitar tamanho
        
        # Buscar documentos por cada palavra-chave (limitado ao limite)
        for palavra in palavras_chave[:limite]:
            try:
                # Codificar a palavra na URL
                palavra_codificada = quote(palavra, safe='')
                response = requests.get(
                    f"{API_URL}/baseconhecimento/get_baseconhecimento_url_documento/{palavra_codificada}",
                    headers=headers,
                    timeout=10
                )
                
                if response.ok:
                    dados = response.json()
                    url_doc = dados.get("url_documento")
                    if url_doc and url_doc not in urls_encontradas:
                        urls_encontradas.append(url_doc)
                        
                        # Se já encontrou o limite, parar
                        if len(urls_encontradas) >= limite:
                            break
            except Exception as e:
                logger.debug(f"Erro ao buscar documento para '{palavra}': {e}")
                continue
        
        # Se não encontrou nada, tentar buscar com o termo completo
        if not urls_encontradas and termo_busca:
            try:
                termo_codificado = quote(termo_busca[:50], safe='')
                response = requests.get(
                    f"{API_URL}/baseconhecimento/get_baseconhecimento_url_documento/{termo_codificado}",
                    headers=headers,
                    timeout=10
                )
                if response.ok:
                    dados = response.json()
                    url_doc = dados.get("url_documento")
                    if url_doc:
                        urls_encontradas.append(url_doc)
            except Exception as e:
                logger.debug(f"Erro ao buscar documento com termo completo: {e}")
        
        logger.info(f"Encontradas {len(urls_encontradas)} URL(s) de documento(s) para '{termo_busca}'")
        return urls_encontradas[:limite]
        
    except Exception as e:
        logger.warning(f"Erro ao buscar URLs de documentos: {e}")
        return []

### AÇÕES DE BUSCA E CONSULTA ###

### CLASSE PARA BUSCAR ÚLTIMOS AVISOS ###
class ActionBuscarUltimosAvisos(Action):
    def name(self) -> Text:
        return "action_buscar_ultimos_avisos"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        # PRIMEIRO: Verificar inatividade (pode deslogar se inativo)
        ainda_autenticado, eventos_inatividade = verificar_e_atualizar_inatividade(tracker, dispatcher)
        if not ainda_autenticado:
            return eventos_inatividade
        
        # SEGUNDO: Verificar autenticação completa
        autenticado, access_token = verificar_autenticacao_completa(tracker)
        if not autenticado:
            dispatcher.utter_message(text="Por favor, faca a autenticacao primeiro. Envie uma saudacao para comecar.")
            logger.warning(f"[{self.name()}] Tentativa de buscar avisos sem autenticacao valida")
            return eventos_inatividade
        
        # Combinar eventos de inatividade (atualização de timestamp) com outros eventos
        eventos = eventos_inatividade
        
        pergunta_aluno = tracker.latest_message.get('text')
        # Salvar pergunta do aluno
        salvar_pergunta_aluno(pergunta_aluno, tracker=tracker)
        
        # Enviar indicador de digitando
        chat_id = obter_chat_id_do_tracker(tracker)
        if chat_id:
            manter_indicador_digitando(chat_id, duracao=15)
        
        logger.info(f"[{self.name()}] Buscando avisos")
        
        # Parar indicador antes de enviar mensagem intermediária
        if chat_id:
            parar_indicador_digitando(chat_id)
        dispatcher.utter_message(text="Consultando mural de avisos...")
        
        # Reiniciar indicador durante processamento
        if chat_id:
            manter_indicador_digitando(chat_id, duracao=10)
        
        try:
            headers = get_auth_headers(tracker, verificar_validade=True)
            response = requests.get(f"{API_URL}/aviso/get_lista_aviso/", headers=headers, timeout=10)
            response.raise_for_status()
            
            # VALIDAÇÃO ADICIONADA
            avisos = ResponseValidator.validate_list_response(response)
            
            # Parar indicador antes de enviar resposta final
            if chat_id:
                parar_indicador_digitando(chat_id)
            
            if not avisos:
                dispatcher.utter_message(text="Nao ha avisos recentes.")
                logger.info(f"[{self.name()}] Nenhum aviso encontrado")
            else:
                mensagem = "Ultimos Avisos:\n\n"
                for aviso in avisos[:3]:
                    if isinstance(aviso, dict):
                        titulo = aviso.get('titulo', 'Aviso')
                        conteudo = aviso.get('conteudo', '')
                        mensagem += f"Titulo: {titulo}\nConteudo: {conteudo}\n----------------\n"
                dispatcher.utter_message(text=mensagem)
                logger.info(f"[{self.name()}] {len(avisos[:3])} avisos retornados")
        except Exception as e:
            ErrorHandler.handle_api_error(
                dispatcher, e,
                context="Buscar avisos",
                action_name=self.name()
            )
        return eventos

### CLASSE PARA BUSCAR CRONOGRAMA DE DISCIPLINA ###
class ActionBuscarCronograma(Action):
    """
    Action para buscar o cronograma/horário de uma disciplina específica.
    Extrai o nome da disciplina da mensagem do usuário e retorna os horários cadastrados.
    """
    def name(self) -> Text:
        return "action_buscar_cronograma"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        # PRIMEIRO: Verificar inatividade (pode deslogar se inativo)
        ainda_autenticado, eventos_inatividade = verificar_e_atualizar_inatividade(tracker, dispatcher)
        if not ainda_autenticado:
            return eventos_inatividade
        
        # SEGUNDO: Verificar autenticação completa
        autenticado, access_token = verificar_autenticacao_completa(tracker)
        if not autenticado:
            dispatcher.utter_message(text="Por favor, faca a autenticacao primeiro. Envie uma saudacao para comecar.")
            logger.warning(f"[{self.name()}] Tentativa de buscar cronograma sem autenticacao valida")
            return eventos_inatividade
        
        pergunta_aluno = tracker.latest_message.get('text')
        # Salvar pergunta do aluno
        salvar_pergunta_aluno(pergunta_aluno, tracker=tracker)
        
        # Iniciar indicador de digitando
        chat_id = iniciar_indicador_em_action(tracker, duracao=20)
        
        disciplina_nome = next(tracker.get_latest_entity_values("disciplina"), None)
        
        # CORREÇÃO: Se não encontrou disciplina, verificar se o usuário respondeu após pergunta anterior
        if not disciplina_nome:
            disciplina_nome = tracker.get_slot("disciplina")
        
        # CORREÇÃO: Tentar extrair disciplina manualmente se não foi extraída
        if not disciplina_nome:
            pergunta_lower = pergunta_aluno.lower()
            palavras_remover = ["é", "de", "a", "o", "da", "do", "das", "dos", "quando", "qual", "horario", "horário", "aula", "tenho", "eu"]
            palavras = pergunta_aluno.split()
            for i, palavra in enumerate(palavras):
                palavra_limpa = palavra.lower().strip('.,!?;:')
                if palavra_limpa not in palavras_remover and len(palavra_limpa) > 2:
                    possivel_disc = ' '.join(palavras[i:i+4])
                    id_test = get_disciplina_id_by_name(possivel_disc, tracker)
                    if id_test:
                        disciplina_nome = possivel_disc
                        logger.info(f"[{self.name()}] Disciplina extraida manualmente: '{disciplina_nome}'")
                        break
        
        if not disciplina_nome:
            parar_indicador_antes_de_resposta(chat_id)
            dispatcher.utter_message(text="De qual disciplina voce quer saber o horario?")
            return []

        logger.info(f"[{self.name()}] Buscando cronograma para disciplina: {disciplina_nome}")
        disciplina_id = get_disciplina_id_by_name(disciplina_nome, tracker)
        
        if not disciplina_id:
            parar_indicador_antes_de_resposta(chat_id)
            dispatcher.utter_message(text=f"Nao encontrei a disciplina {disciplina_nome}.")
            logger.warning(f"[{self.name()}] Disciplina '{disciplina_nome}' nao encontrada")
            return []

        try:
            headers = get_auth_headers(tracker, verificar_validade=True)
            if "Authorization" not in headers:
                dispatcher.utter_message(text="Sessao expirada. Por favor, faca a autenticacao novamente enviando uma saudacao.")
                logger.error(f"[{self.name()}] Token de autenticacao nao disponivel ou invalido")
                return []
            
            response = requests.get(f"{API_URL}/cronograma/disciplina/{disciplina_id}", headers=headers, timeout=10)
            response.raise_for_status()
            
            # VALIDAÇÃO ADICIONADA
            cronogramas = ResponseValidator.validate_list_response(response)
            
            # Parar indicador antes de enviar resposta
            parar_indicador_antes_de_resposta(chat_id)
            
            if not cronogramas:
                dispatcher.utter_message(text=f"Sem horarios cadastrados para {disciplina_nome}.")
                logger.info(f"[{self.name()}] Nenhum cronograma encontrado para '{disciplina_nome}'")
            else:
                # Mapear número do dia para nome
                dias_semana = {
                    1: "Segunda-feira",
                    2: "Terça-feira",
                    3: "Quarta-feira",
                    4: "Quinta-feira",
                    5: "Sexta-feira",
                    6: "Sábado",
                    7: "Domingo"
                }
                
                msg = f"Horario de {disciplina_nome}:\n"
                for item in cronogramas:
                    if isinstance(item, dict):
                        # Verificar se id_disciplina corresponde à disciplina buscada (filtro adicional)
                        item_id_disc = item.get('id_disciplina')
                        if item_id_disc and item_id_disc != disciplina_id:
                            # Pular se não for da disciplina correta
                            logger.warning(f"[{self.name()}] Item de outra disciplina encontrado: {item_id_disc} != {disciplina_id}")
                            continue
                        
                        dia_num = item.get('dia_semana', '')
                        # Converter número para nome do dia se necessário
                        if isinstance(dia_num, int):
                            dia = dias_semana.get(dia_num, f"Dia {dia_num}")
                        elif isinstance(dia_num, str) and dia_num.isdigit():
                            dia = dias_semana.get(int(dia_num), f"Dia {dia_num}")
                        else:
                            dia = dia_num if dia_num else 'N/A'
                        
                        inicio = item.get('hora_inicio', '')
                        sala = item.get('sala', 'N/A')
                        msg += f"- {dia} as {inicio} (Sala {sala})\n"
                    else:
                        logger.warning(f"[{self.name()}] Item do cronograma nao e dict: {type(item)}")
                
                dispatcher.utter_message(text=msg)
                logger.info(f"[{self.name()}] {len(cronogramas)} cronograma(s) retornado(s) para '{disciplina_nome}'")

        except Exception as e:
            ErrorHandler.handle_api_error(
                dispatcher, e,
                context=f"Buscar cronograma - disciplina {disciplina_nome}",
                action_name=self.name()
            )
        return []

### CLASSE PARA GERAR RESPOSTA COM IA ###
class ActionGerarRespostaComIA(Action):
    """
    Action para gerar resposta usando IA (base de conhecimento).
    Busca informações na base de conhecimento e retorna resposta contextualizada.
    Também inclui URLs de documentos relacionados quando disponíveis.
    """
    def name(self) -> Text:
        return "action_gerar_resposta_com_ia"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        pergunta_aluno = tracker.latest_message.get('text')
        
        # PRIMEIRO: Verificar inatividade (pode deslogar se inativo)
        ainda_autenticado, eventos_inatividade = verificar_e_atualizar_inatividade(tracker, dispatcher)
        if not ainda_autenticado:
            return eventos_inatividade
        
        # SEGUNDO: Verificar autenticação completa (incluindo validade do token)
        autenticado, access_token = verificar_autenticacao_completa(tracker)
        
        if not autenticado or not access_token:
            dispatcher.utter_message(text="Por favor, faca a autenticacao primeiro. Envie uma saudacao para comecar.")
            logger.warning(f"[{self.name()}] Tentativa de usar IA sem autenticacao valida. autenticado={autenticado}, token_presente={bool(access_token)}")
            return eventos_inatividade
        
        # Salvar pergunta do aluno
        salvar_pergunta_aluno(pergunta_aluno, tracker=tracker)
        
        # Enviar indicador de digitando no Telegram
        chat_id = obter_chat_id_do_tracker(tracker)
        if chat_id:
            enviar_indicador_digitando(chat_id)
            # Manter indicador ativo durante a requisição (pode demorar até 30 segundos)
            manter_indicador_digitando(chat_id, duracao=30)
        
        dispatcher.utter_message(text="Consultando Base de Dados...")

        try:
            # --- ESTA É A CORREÇÃO ---
            # Agora enviamos APENAS o campo "pergunta", exatamente
            # como a sua nova API (ia_services.py) espera.
            payload = {
                "pergunta": pergunta_aluno
            }
            # ---------------------------

            logger.info(f"[{self.name()}] Gerando resposta da IA para: {pergunta_aluno[:50]}...")
            
            # Obter headers com token de autenticação válido
            headers = get_auth_headers(tracker, verificar_validade=True)
            
            # Verificar se o token foi incluído nos headers
            if "Authorization" not in headers:
                dispatcher.utter_message(text="Sessao expirada. Por favor, faca a autenticacao novamente enviando uma saudacao.")
                logger.error(f"[{self.name()}] Token de autenticacao nao disponivel ou invalido")
                return []
            
            response = requests.post(
                f"{API_URL}/ia/gerar-resposta", 
                json=payload, 
                headers=headers,
                timeout=30
            )
            response.raise_for_status()
            
            # VALIDAÇÃO ADICIONADA
            dados = ResponseValidator.validate_json_response(response, expected_keys=["resposta"])
            
            if not dados:
                dispatcher.utter_message(text="A IA processou mas nao retornou uma resposta valida.")
                logger.warning(f"[{self.name()}] Resposta invalida da IA")
                return []
            
            texto_resposta = dados.get("resposta", "A IA processou mas nao retornou texto.")
            
            # NOVO: Buscar URLs dos documentos usados como referência
            try:
                # Usar função helper para buscar URLs de documentos relacionados
                # Passar headers de autenticação
                urls_documentos = buscar_urls_documentos_relacionados(pergunta_aluno, limite=3, headers=headers)
                
                if urls_documentos:
                    texto_resposta += "\n\nDocumentos de referencia:\n"
                    for i, url in enumerate(urls_documentos, 1):
                        texto_resposta += f"{i}. {url}\n"
                    logger.info(f"[{self.name()}] {len(urls_documentos)} URL(s) de referencia adicionada(s)")
            except Exception as e:
                logger.warning(f"[{self.name()}] Erro ao buscar URLs de referencia: {e}")
                # Se falhar, não interrompe a resposta principal
            
            # Parar indicador antes de enviar resposta final
            if chat_id:
                parar_indicador_digitando(chat_id)
            
            dispatcher.utter_message(text=texto_resposta)
            logger.info(f"[{self.name()}] Resposta da IA gerada com sucesso")

        except Exception as e:
            ErrorHandler.handle_api_error(
                dispatcher, e,
                context=f"Gerar resposta IA - pergunta: {pergunta_aluno[:50]}...",
                action_name=self.name()
            ) 
            
        return []

### CLASSE PARA BUSCAR DATA DE AVALIAÇÃO ###
class ActionBuscarDataAvaliacao(Action):
    """
    Action para buscar datas de avaliações (provas) de uma disciplina.
    Suporta diferentes tipos de avaliação (NP1, NP2, SUB, EXAME).
    Também redireciona para cronograma se a pergunta for sobre horário de aula.
    """
    def name(self) -> Text:
        return "action_buscar_data_avaliacao"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        # PRIMEIRO: Verificar inatividade (pode deslogar se inativo)
        ainda_autenticado, eventos_inatividade = verificar_e_atualizar_inatividade(tracker, dispatcher)
        if not ainda_autenticado:
            return eventos_inatividade
        
        # SEGUNDO: Verificar autenticação completa
        autenticado, access_token = verificar_autenticacao_completa(tracker)
        if not autenticado:
            dispatcher.utter_message(text="Por favor, faca a autenticacao primeiro. Envie uma saudacao para comecar.")
            logger.warning(f"[{self.name()}] Tentativa de buscar data avaliacao sem autenticacao valida")
            return eventos_inatividade
        
        pergunta_aluno = tracker.latest_message.get('text')
        # Salvar pergunta do aluno
        salvar_pergunta_aluno(pergunta_aluno, tracker=tracker)
        
        # Enviar indicador de digitando
        chat_id = obter_chat_id_do_tracker(tracker)
        if chat_id:
            enviar_indicador_digitando(chat_id)
        
        # CORREÇÃO: Verificar se a pergunta é sobre "aula" e redirecionar para action_buscar_cronograma
        # MAS NÃO redirecionar se mencionar "prova" ou se o contexto anterior é sobre provas
        pergunta_lower = pergunta_aluno.lower()
        ultima_consulta_tipo = tracker.get_slot("ultima_consulta_tipo")
        
        # Palavras que indicam pergunta sobre PROVA/AVALIAÇÃO
        palavras_prova = ["prova", "provas", "avaliacao", "avaliação", "np1", "np2", "sub", "exame", "substitutiva"]
        
        # Palavras que indicam pergunta sobre HORÁRIO (podem ser de aula ou prova)
        palavras_horario = ["horario", "horário", "horas", "que horas", "qual horario", "qual horário", "em que horario", "em que horário"]
        
        # Palavras que indicam pergunta sobre AULA (específico de aula, não prova)
        palavras_aula_especifica = ["aula", "aulas", "quando tenho aula", "quando e a aula", "quando é a aula"]
        
        # Verificar se menciona prova/avaliação
        menciona_prova = any(palavra in pergunta_lower for palavra in palavras_prova)
        
        # Verificar se menciona horário
        menciona_horario = any(palavra in pergunta_lower for palavra in palavras_horario)
        
        # Verificar se menciona aula especificamente
        menciona_aula = any(palavra in pergunta_lower for palavra in palavras_aula_especifica)
        
        # Verificar contexto anterior
        contexto_prova = ultima_consulta_tipo == "prova"
        
        # Verificar se há tipo de avaliação na entidade (indica pergunta sobre prova)
        tem_tipo_avaliacao = next(tracker.get_latest_entity_values("tipo_avaliacao"), None) is not None
        
        # LÓGICA: Só redirecionar para cronograma se:
        # 1. Menciona "aula" especificamente OU menciona horário mas SEM mencionar prova
        # 2. NÃO menciona "prova", "np1", "np2", etc.
        # 3. NÃO tem tipo_avaliacao na entidade
        # 4. O contexto anterior NÃO é sobre "prova"
        # 5. Se menciona apenas horário sem contexto, assumir que é sobre aula (não prova)
        
        if menciona_prova or tem_tipo_avaliacao or contexto_prova:
            # Se menciona prova ou tem contexto de prova, NÃO redirecionar para cronograma
            # Continuar com a lógica de buscar avaliação
            pass
        elif menciona_aula:
            # Se menciona "aula" especificamente e não menciona prova, é sobre horário de aula
            action_cronograma = ActionBuscarCronograma()
            return action_cronograma.run(dispatcher, tracker, domain)
        elif menciona_horario and not menciona_prova:
            # Se menciona horário mas não menciona prova e não tem contexto de prova, 
            # pode ser sobre aula. Mas vamos verificar se há disciplina mencionada
            # Se não há contexto de prova, assumir que é sobre aula
            action_cronograma = ActionBuscarCronograma()
            return action_cronograma.run(dispatcher, tracker, domain)
        
        # Verificar se é pergunta sobre todas as provas (sem disciplina específica)
        palavras_todas_provas = ["quais sao as provas", "lista todas as provas", "quais provas estao marcadas", 
                                  "todas as provas", "provas marcadas", "lista de avaliacoes", "quais avaliacoes tem",
                                  "quais provas eu tenho esse semestre", "quais avaliacoes eu tenho esse semestre"]
        if any(palavra in pergunta_lower for palavra in palavras_todas_provas):
            # Chamar action para listar todas as provas
            action_listar = ActionListarTodasProvas()
            return action_listar.run(dispatcher, tracker, domain)
        
        # Verificar se é pergunta sobre provas em mês específico
        # NOTA: ActionBuscarProvasPorMes não está implementada - usar listagem geral
        mes_entidade = next(tracker.get_latest_entity_values("mes"), None)
        if mes_entidade or any(mes in pergunta_lower for mes in ["novembro", "dezembro", "outubro", "setembro", "agosto", "julho", "junho", "maio", "abril", "marco", "fevereiro", "janeiro"]):
            # TODO: Implementar ActionBuscarProvasPorMes para filtrar provas por mês
            # Por enquanto, usar ActionListarTodasProvas como fallback
            logger.info(f"[{self.name()}] Pergunta sobre provas por mes detectada. Usando listagem geral.")
            action_listar = ActionListarTodasProvas()
            return action_listar.run(dispatcher, tracker, domain)
        
        disciplina_nome = next(tracker.get_latest_entity_values("disciplina"), None)
        termo_busca = next(tracker.get_latest_entity_values("tipo_avaliacao"), None)
        
        # CORREÇÃO: Se não encontrou tipo_avaliacao, verificar se é pergunta de seguimento
        if not termo_busca:
            # Verificar se há tipo de avaliação no slot (pode ter sido preenchido em resposta anterior)
            termo_busca = tracker.get_slot("ultima_avaliacao_tipo")
            # Se ainda não encontrou, verificar no texto da pergunta
            if not termo_busca:
                pergunta_lower = pergunta_aluno.lower()
                if "np1" in pergunta_lower:
                    termo_busca = "np1"
                elif "np2" in pergunta_lower:
                    termo_busca = "np2"
                elif "sub" in pergunta_lower or "substitutiva" in pergunta_lower:
                    termo_busca = "sub"
                elif "exame" in pergunta_lower:
                    termo_busca = "exame"
                else:
                    termo_busca = "prova"  # Padrão: retornar todas as provas
        
        # CORREÇÃO: Se não encontrou disciplina, verificar contexto de pergunta anterior
        if not disciplina_nome:
            # Verificar se há disciplina no slot (pode ter sido preenchida em resposta anterior)
            disciplina_nome = tracker.get_slot("disciplina")
            # CORREÇÃO: Se ainda não encontrou, verificar contexto de consulta anterior
            if not disciplina_nome:
                disciplina_nome = tracker.get_slot("ultima_disciplina_consultada")
                if disciplina_nome:
                    logger.info(f"[{self.name()}] Usando disciplina do contexto anterior: '{disciplina_nome}'")
        
        # CORREÇÃO: Extrair disciplina manualmente se não foi extraída
        # O problema é que "é" pode ser confundido com disciplina
        if not disciplina_nome:
            # Tentar extrair manualmente do texto
            palavras_remover = ["é", "de", "a", "o", "da", "do", "das", "dos", "quando", "qual", "aula", "avaliacao", "avaliação", "prova", "provas", "sera", "será", "tenho", "tenho?", "em", "esse", "semestre", "a", "o"]
            palavras = pergunta_aluno.split()
            # Procurar por palavras que podem ser nomes de disciplinas
            for i, palavra in enumerate(palavras):
                palavra_limpa = palavra.lower().strip('.,!?;:')
                if palavra_limpa not in palavras_remover and len(palavra_limpa) > 2:
                    # Tentar buscar disciplina com essa palavra ou combinação
                    possivel_disc = ' '.join(palavras[i:i+4])  # Pegar até 4 palavras consecutivas
                    id_test = get_disciplina_id_by_name(possivel_disc, tracker)
                    if id_test:
                        disciplina_nome = possivel_disc
                        logger.info(f"[{self.name()}] Disciplina extraida manualmente: '{disciplina_nome}'")
                        break

        if not disciplina_nome:
            dispatcher.utter_message(text="Qual a disciplina?")
            return []  # Não limpar slot - permite que usuário responda e seja capturado

        id_disciplina = get_disciplina_id_by_name(disciplina_nome, tracker)
        if not id_disciplina:
             dispatcher.utter_message(text=f"Disciplina '{disciplina_nome}' nao encontrada. Verifique se o nome esta correto.")
             return []

        logger.info(f"[{self.name()}] Buscando avaliacoes para disciplina: {disciplina_nome}, tipo: {termo_busca}")
        
        try:
            headers = get_auth_headers(tracker, verificar_validade=True)
            if "Authorization" not in headers:
                dispatcher.utter_message(text="Sessao expirada. Por favor, faca a autenticacao novamente enviando uma saudacao.")
                logger.error(f"[{self.name()}] Token de autenticacao nao disponivel ou invalido")
                return []
            
            response = requests.get(f"{API_URL}/avaliacao/disciplina/{id_disciplina}", headers=headers, timeout=10)
            response.raise_for_status()
            
            # VALIDAÇÃO ADICIONADA
            avaliacoes = ResponseValidator.validate_list_response(response)
            
            encontradas = []
            termo_busca_lower = termo_busca.lower()
            
            # CORREÇÃO: Verificar se a pergunta pede horário das provas
            ultima_consulta_tipo = tracker.get_slot("ultima_consulta_tipo")
            palavras_horario = ["horario", "horário", "que horas", "hora", "qual o horario", "qual o horário", "em que horario", "em que horário"]
            pede_horario = any(palavra in pergunta_lower for palavra in palavras_horario)
            contexto_prova = ultima_consulta_tipo == "prova"
            
            # SEMPRE incluir horário se:
            # 1. A pergunta menciona palavras de horário (ex: "que horas é a np1?")
            # 2. OU o contexto anterior é sobre provas e a pergunta menciona horário
            # 3. OU a intent foi classificada como consultar_data_avaliacao e menciona horário
            incluir_horario = pede_horario or (contexto_prova and pede_horario)
            
            for aval in avaliacoes:
                if not isinstance(aval, dict):
                    logger.warning(f"[{self.name()}] Item de avaliacao nao e dict: {type(aval)}")
                    continue
                    
                tipo_aval = aval.get('tipo_avaliacao', '')
                data_aval = aval.get('data_prova', '')  # CORREÇÃO: campo correto da API
                hora_inicio = aval.get('hora_inicio', '')
                hora_fim = aval.get('hora_fim', '')
                sala = aval.get('sala', '')
                
                # Pular se tipo ou data forem None
                if not tipo_aval or not data_aval:
                    continue
                
                tipo_aval_lower = tipo_aval.lower()
                
                # Função auxiliar para formatar data no padrão brasileiro (DD/MM/YYYY)
                def formatar_data_br(data_str):
                    """Converte data de YYYY-MM-DD para DD/MM/YYYY"""
                    try:
                        # Remove parte do tempo se houver
                        data_limpa = data_str.split('T')[0] if 'T' in data_str else data_str
                        # Parse da data
                        data_obj = datetime.strptime(data_limpa, '%Y-%m-%d')
                        # Retorna no formato brasileiro
                        return data_obj.strftime('%d/%m/%Y')
                    except (ValueError, AttributeError) as e:
                        logger.warning(f"[{self.name()}] Erro ao formatar data '{data_str}': {e}")
                        # Se falhar, retorna a data original
                        return data_limpa if 'data_limpa' in locals() else data_str
                
                # Função auxiliar para formatar horário
                def formatar_horario(hora_str):
                    """Formata horário HH:MM:SS para HH:MM"""
                    if not hora_str or hora_str == "00:00" or hora_str == "00:00:00":
                        return None
                    try:
                        # Se já está no formato HH:MM, retorna
                        if len(hora_str) == 5:
                            return hora_str
                        # Se está no formato HH:MM:SS, remove os segundos
                        if len(hora_str) >= 5:
                            return hora_str[:5]
                        return hora_str
                    except Exception:
                        return hora_str
                
                # Montar string de data e horário
                data_fmt = formatar_data_br(data_aval)
                hora_inicio_fmt = formatar_horario(hora_inicio) if incluir_horario else None
                hora_fim_fmt = formatar_horario(hora_fim) if incluir_horario else None
                
                # Montar mensagem com data e horário (se solicitado)
                horario_str = ""
                if incluir_horario and hora_inicio_fmt:
                    if hora_fim_fmt and hora_fim_fmt != hora_inicio_fmt and hora_fim_fmt != "00:00":
                        horario_str = f" {hora_inicio_fmt} às {hora_fim_fmt}"
                    else:
                        horario_str = f" {hora_inicio_fmt}"
                    if sala:
                        horario_str += f" (Sala {sala})"
                
                # Melhorar filtro de busca - CORREÇÃO: retornar todas as provas quando busca genérica
                if termo_busca_lower in ["prova", "provas", "avaliacao", "avaliação", ""]:
                    # Se busca genérica "prova" ou vazio, retorna TODAS (NP1, NP2, SUB, EXAME)
                    encontradas.append(f"- {tipo_aval}: {data_fmt}{horario_str}")
                elif termo_busca_lower == "np1" and tipo_aval_lower == "np1":
                    encontradas.append(f"- {tipo_aval}: {data_fmt}{horario_str}")
                elif termo_busca_lower == "np2" and tipo_aval_lower == "np2":
                    encontradas.append(f"- {tipo_aval}: {data_fmt}{horario_str}")
                elif termo_busca_lower in ["sub", "substitutiva"] and tipo_aval_lower == "sub":
                    # CORREÇÃO: Reconhecer SUB mesmo sem "prova" antes
                    encontradas.append(f"- {tipo_aval}: {data_fmt}{horario_str}")
                elif termo_busca_lower == "exame" and tipo_aval_lower == "exame":
                    encontradas.append(f"- {tipo_aval}: {data_fmt}{horario_str}")

            # Parar indicador antes de enviar resposta
            chat_id = obter_chat_id_do_tracker(tracker)
            parar_indicador_antes_de_resposta(chat_id)
            
            if encontradas:
                # Verificar se a pergunta pede horário para ajustar o título
                pede_horario = any(palavra in pergunta_lower for palavra in ["horario", "horário", "que horas", "hora"])
                titulo = "Datas e Horários:" if pede_horario or incluir_horario else "Datas:"
                dispatcher.utter_message(text=f"{titulo}\n" + "\n".join(encontradas))
                logger.info(f"[{self.name()}] {len(encontradas)} avaliacao(oes) encontrada(s)")
            else:
                dispatcher.utter_message(text=f"Nao achei datas de {termo_busca} para essa materia.")
                logger.info(f"[{self.name()}] Nenhuma avaliacao encontrada para '{termo_busca}'")
                
        except Exception as e:
            ErrorHandler.handle_api_error(
                dispatcher, e,
                context=f"Buscar avaliacoes - disciplina {disciplina_nome}, tipo {termo_busca}",
                action_name=self.name()
            )
        return []

### CLASSE PARA BUSCAR CONTEÚDO DE AVALIAÇÃO ###
class ActionBuscarConteudoAvaliacao(Action):
    """
    Action para buscar o conteúdo programático de uma avaliação específica.
    Suporta diferentes tipos de avaliação (NP1, NP2, SUB, EXAME).
    Verifica se a disciplina é AVA e retorna mensagem apropriada.
    """
    def name(self) -> Text:
        return "action_buscar_conteudo_avaliacao"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        # PRIMEIRO: Verificar inatividade (pode deslogar se inativo)
        ainda_autenticado, eventos_inatividade = verificar_e_atualizar_inatividade(tracker, dispatcher)
        if not ainda_autenticado:
            return eventos_inatividade
        
        # SEGUNDO: Verificar autenticação completa
        autenticado, access_token = verificar_autenticacao_completa(tracker)
        if not autenticado:
            dispatcher.utter_message(text="Por favor, faca a autenticacao primeiro. Envie uma saudacao para comecar.")
            logger.warning(f"[{self.name()}] Tentativa de buscar conteudo avaliacao sem autenticacao valida")
            return eventos_inatividade
        
        pergunta_aluno = tracker.latest_message.get('text')
        salvar_pergunta_aluno(pergunta_aluno, tracker=tracker)
        
        # Enviar indicador de digitando
        chat_id = obter_chat_id_do_tracker(tracker)
        if chat_id:
            enviar_indicador_digitando(chat_id)
        
        pergunta_lower = pergunta_aluno.lower()
        
        # Extrair disciplina
        disciplina_nome = next(tracker.get_latest_entity_values("disciplina"), None)
        
        # Se não encontrou disciplina, verificar contexto
        if not disciplina_nome:
            disciplina_nome = tracker.get_slot("disciplina")
            if not disciplina_nome:
                disciplina_nome = tracker.get_slot("ultima_disciplina_consultada")
                if disciplina_nome:
                    logger.info(f"[{self.name()}] Usando disciplina do contexto anterior: '{disciplina_nome}'")
        
        # Mapear abreviações
        # NOTA: Método _mapear_abreviacao_para_nome_completo não está implementado em CacheHelper
        # TODO: Implementar mapeamento de abreviações ou remover esta funcionalidade
        # if disciplina_nome:
        #     disciplina_nome = CacheHelper._mapear_abreviacao_para_nome_completo(disciplina_nome)
        
        # Extrair tipo de avaliação
        tipo_avaliacao = next(tracker.get_latest_entity_values("tipo_avaliacao"), None)
        
        # Se não encontrou tipo, verificar contexto
        if not tipo_avaliacao:
            tipo_avaliacao = tracker.get_slot("ultima_avaliacao_tipo")
            if not tipo_avaliacao:
                # Tentar extrair do texto
                if "np1" in pergunta_lower:
                    tipo_avaliacao = "NP1"
                elif "np2" in pergunta_lower:
                    tipo_avaliacao = "NP2"
                elif "sub" in pergunta_lower or "substitutiva" in pergunta_lower:
                    tipo_avaliacao = "SUB"
                elif "exame" in pergunta_lower:
                    tipo_avaliacao = "EXAME"
        
        # Se não tem tipo de avaliação, perguntar qual prova
        if not tipo_avaliacao:
            dispatcher.utter_message(text="Qual prova voce quer saber o conteudo? (NP1, NP2, SUB ou EXAME)")
            return []
        
        # Se não tem disciplina, tentar extrair manualmente
        if not disciplina_nome:
            palavras_remover = ["é", "de", "a", "o", "da", "do", "das", "dos", "qual", "o", "conteudo", "conteúdo", "da", "prova", "avaliacao", "avaliação", "cai", "vai", "materia", "matéria"]
            palavras = pergunta_aluno.split()
            for i, palavra in enumerate(palavras):
                palavra_limpa = palavra.lower().strip('.,!?;:')
                if palavra_limpa not in palavras_remover and len(palavra_limpa) > 2:
                    possivel_disc = ' '.join(palavras[i:i+4])
                    id_test = get_disciplina_id_by_name(possivel_disc, tracker)
                    if id_test:
                        disciplina_nome = possivel_disc
                        logger.info(f"[{self.name()}] Disciplina extraida manualmente: '{disciplina_nome}'")
                        break
        
        if not disciplina_nome:
            dispatcher.utter_message(text="Qual disciplina voce quer saber o conteudo?")
            return []
        
        # Obter ID da disciplina
        id_disciplina = get_disciplina_id_by_name(disciplina_nome, tracker)
        if not id_disciplina:
            dispatcher.utter_message(text=f"Disciplina '{disciplina_nome}' nao encontrada. Verifique se o nome esta correto.")
            return []
        
        # CORREÇÃO: Verificar se a disciplina é AVA
        # Buscar informações da disciplina para verificar se é AVA
        try:
            headers = get_auth_headers(tracker, verificar_validade=True)
            response_disc = requests.get(f"{API_URL}/disciplinas/lista_disciplina/", headers=headers, timeout=10)
            if response_disc.ok:
                disciplinas = ResponseValidator.validate_list_response(response_disc)
                if disciplinas:
                    for disc in disciplinas:
                        if isinstance(disc, dict):
                            disc_id = disc.get('id_disciplina')
                            # Comparar IDs (pode ser string ou UUID)
                            if str(disc_id) == str(id_disciplina):
                                nome_disc = disc.get('nome_disciplina', '')
                                # Verificar se contém "AVA" no nome (pode ser variações como "AVA", "Ava", etc)
                                if nome_disc and ('ava' in nome_disc.lower() or 'ambiente virtual' in nome_disc.lower()):
                                    dispatcher.utter_message(text="Os conteudos das avaliacoes dos Avas estao disponiveis no site da UNIP.")
                                    logger.info(f"[{self.name()}] Disciplina '{disciplina_nome}' e AVA. Retornando mensagem padrao.")
                                    return []
                                break
        except Exception as e:
            logger.debug(f"[{self.name()}] Erro ao verificar se disciplina e AVA: {e}")
        
        logger.info(f"[{self.name()}] Buscando conteudo da avaliacao {tipo_avaliacao} para disciplina: {disciplina_nome}")
        
        try:
            # Buscar avaliações da disciplina
            headers = get_auth_headers(tracker, verificar_validade=True)
            if "Authorization" not in headers:
                dispatcher.utter_message(text="Sessao expirada. Por favor, faca a autenticacao novamente enviando uma saudacao.")
                logger.error(f"[{self.name()}] Token de autenticacao nao disponivel ou invalido")
                return []
            
            response = requests.get(f"{API_URL}/avaliacao/disciplina/{id_disciplina}", headers=headers, timeout=10)
            response.raise_for_status()
            
            avaliacoes = ResponseValidator.validate_list_response(response)
            
            # Procurar a avaliação do tipo especificado
            conteudo_encontrado = None
            tipo_avaliacao_lower = tipo_avaliacao.lower()
            
            for aval in avaliacoes:
                if not isinstance(aval, dict):
                    continue
                
                tipo_aval = aval.get('tipo_avaliacao', '').lower()
                conteudo = aval.get('conteudo', '')
                
                # Verificar se é o tipo de avaliação procurado
                if tipo_aval == tipo_avaliacao_lower or (tipo_avaliacao_lower == "np1" and tipo_aval == "np1") or \
                   (tipo_avaliacao_lower == "np2" and tipo_aval == "np2") or \
                   (tipo_avaliacao_lower == "sub" and tipo_aval == "sub") or \
                   (tipo_avaliacao_lower == "exame" and tipo_aval == "exame"):
                    if conteudo:
                        conteudo_encontrado = conteudo
                        break
            
            if conteudo_encontrado:
                mensagem = f"Conteudo da {tipo_avaliacao.upper()} de {disciplina_nome}:\n\n{conteudo_encontrado}"
                dispatcher.utter_message(text=mensagem)
                logger.info(f"[{self.name()}] Conteudo da {tipo_avaliacao} encontrado para {disciplina_nome}")
                # Salvar contexto
                return [
                    SlotSet("ultima_disciplina_consultada", disciplina_nome),
                    SlotSet("ultima_consulta_tipo", "conteudo"),
                    SlotSet("ultima_avaliacao_tipo", tipo_avaliacao)
                ]
            else:
                dispatcher.utter_message(text=f"Nao encontrei o conteudo da {tipo_avaliacao.upper()} para {disciplina_nome}.")
                logger.info(f"[{self.name()}] Conteudo da {tipo_avaliacao} nao encontrado para {disciplina_nome}")
                
        except Exception as e:
            ErrorHandler.handle_api_error(
                dispatcher, e,
                context=f"Buscar conteudo avaliacao - disciplina {disciplina_nome}, tipo {tipo_avaliacao}",
                action_name=self.name()
            )
        
        return []

### CLASSE PARA LISTAR TODAS AS PROVAS ###
class ActionListarTodasProvas(Action):
    """
    Action para listar todas as provas agendadas de todas as disciplinas do aluno.
    Busca todas as disciplinas e suas respectivas avaliações, formatando as informações.
    """
    def name(self) -> Text:
        return "action_listar_todas_provas"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        # PRIMEIRO: Verificar inatividade (pode deslogar se inativo)
        ainda_autenticado, eventos_inatividade = verificar_e_atualizar_inatividade(tracker, dispatcher)
        if not ainda_autenticado:
            return eventos_inatividade
        
        # SEGUNDO: Verificar autenticação completa
        autenticado, access_token = verificar_autenticacao_completa(tracker)
        if not autenticado:
            dispatcher.utter_message(text="Por favor, faca a autenticacao primeiro. Envie uma saudacao para comecar.")
            logger.warning(f"[{self.name()}] Tentativa de listar provas sem autenticacao valida")
            return eventos_inatividade
        
        pergunta_aluno = tracker.latest_message.get('text')
        # Salvar pergunta do aluno
        salvar_pergunta_aluno(pergunta_aluno, tracker=tracker)
        
        # Enviar indicador de digitando
        chat_id = obter_chat_id_do_tracker(tracker)
        if chat_id:
            enviar_indicador_digitando(chat_id)
            manter_indicador_digitando(chat_id, duracao=30)
        
        logger.info(f"[{self.name()}] Listando todas as provas")
        dispatcher.utter_message(text="Buscando todas as provas agendadas...")
        
        try:
            # SOLUÇÃO: Buscar lista de disciplinas e depois buscar avaliações para cada uma
            disciplinas_map = {}  # Map id -> nome
            avaliacoes_por_disciplina = {}
            
            # 1. Buscar lista de todas as disciplinas
            logger.info(f"[{self.name()}] Buscando lista de disciplinas")
            headers = get_auth_headers(tracker, verificar_validade=True)
            if "Authorization" not in headers:
                dispatcher.utter_message(text="Sessao expirada. Por favor, faca a autenticacao novamente enviando uma saudacao.")
                logger.error(f"[{self.name()}] Token de autenticacao nao disponivel ou invalido")
                return []
            
            response_disciplinas = requests.get(f"{API_URL}/disciplinas/lista_disciplina/", headers=headers, timeout=10)
            
            if not response_disciplinas.ok:
                dispatcher.utter_message(text="Nao foi possivel buscar a lista de disciplinas no momento.")
                logger.warning(f"[{self.name()}] Erro ao buscar lista de disciplinas: {response_disciplinas.status_code}")
                return []
            
            disciplinas = ResponseValidator.validate_list_response(response_disciplinas)
            
            if not disciplinas:
                dispatcher.utter_message(text="Nao ha disciplinas cadastradas no momento.")
                logger.info(f"[{self.name()}] Nenhuma disciplina encontrada")
                return []
            
            # Criar map de disciplinas
            for disc in disciplinas:
                if isinstance(disc, dict):
                    id_disc = disc.get('id_disciplina')
                    nome_disc = disc.get('nome_disciplina')
                    if id_disc and nome_disc:
                        disciplinas_map[id_disc] = nome_disc
            
            logger.info(f"[{self.name()}] {len(disciplinas_map)} disciplina(s) encontrada(s)")
            
            # 2. Buscar avaliações para cada disciplina
            total_avaliacoes = 0
            for id_disciplina, nome_disciplina in disciplinas_map.items():
                try:
                    headers = get_auth_headers(tracker, verificar_validade=True)
                    response_aval = requests.get(
                        f"{API_URL}/avaliacao/disciplina/{id_disciplina}",
                        headers=headers,
                        timeout=10
                    )
                    
                    if response_aval.ok:
                        avaliacoes = ResponseValidator.validate_list_response(response_aval)
                        
                        if avaliacoes:
                            if nome_disciplina not in avaliacoes_por_disciplina:
                                avaliacoes_por_disciplina[nome_disciplina] = []
                            
                            for aval in avaliacoes:
                                if isinstance(aval, dict):
                                    tipo_aval = aval.get('tipo_avaliacao', '')
                                    data_prova = aval.get('data_prova', '')
                                    hora_inicio = aval.get('hora_inicio', '')
                                    
                                    if tipo_aval and data_prova:
                                        # Formatar data no padrão brasileiro
                                        try:
                                            data_limpa = data_prova.split('T')[0] if 'T' in data_prova else data_prova
                                            data_obj = datetime.strptime(data_limpa, '%Y-%m-%d')
                                            data_fmt = data_obj.strftime('%d/%m/%Y')
                                        except (ValueError, AttributeError):
                                            data_fmt = data_prova.split('T')[0] if 'T' in data_prova else data_prova
                                        
                                        # Formatar horário de início (apenas se não for 00:00)
                                        hora_fmt = None
                                        if hora_inicio and hora_inicio != "00:00" and hora_inicio != "00:00:00":
                                            try:
                                                # Formatar para HH:MM
                                                if len(hora_inicio) >= 5:
                                                    hora_fmt = hora_inicio[:5]
                                                else:
                                                    hora_fmt = hora_inicio
                                            except Exception:
                                                hora_fmt = hora_inicio
                                        

                                        avaliacoes_por_disciplina[nome_disciplina].append({
                                            'tipo': tipo_aval,
                                            'data': data_fmt,
                                            'hora': hora_fmt
                                        })
                                        total_avaliacoes += 1
                except Exception as e:
                    logger.debug(f"[{self.name()}] Erro ao buscar avaliacoes para disciplina {nome_disciplina}: {e}")
                    continue
            
            # 3. Montar mensagem
            if avaliacoes_por_disciplina:
                msg = "Provas Agendadas:\n\n"
                for disc_nome in sorted(avaliacoes_por_disciplina.keys()):
                    msg += f"{disc_nome}:\n"
                    for aval in avaliacoes_por_disciplina[disc_nome]:
                        hora_str = f" às {aval['hora']}" if aval.get('hora') else ""
                        msg += f"  - {aval['tipo']}: {aval['data']}{hora_str}\n"
                    msg += "\n"
                
                dispatcher.utter_message(text=msg)
                logger.info(f"[{self.name()}] {total_avaliacoes} avaliacao(oes) listada(s) de {len(avaliacoes_por_disciplina)} disciplina(s)")
            else:
                dispatcher.utter_message(text="Nao ha provas agendadas no momento.")
                logger.info(f"[{self.name()}] Nenhuma avaliacao encontrada")
                
        except Exception as e:
            ErrorHandler.handle_api_error(
                dispatcher, e,
                context="Listar todas as provas",
                action_name=self.name()
            )
        
        return []

### CLASSE PARA BUSCAR INFORMAÇÕES DE ATIVIDADE ACADÊMICA ###
class ActionBuscarInfoAtividadeAcademica(Action):
    def name(self) -> Text:
        return "action_buscar_info_atividade_academica"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        # PRIMEIRO: Verificar inatividade (pode deslogar se inativo)
        ainda_autenticado, eventos_inatividade = verificar_e_atualizar_inatividade(tracker, dispatcher)
        if not ainda_autenticado:
            return eventos_inatividade
        
        # SEGUNDO: Verificar autenticação completa
        autenticado, access_token = verificar_autenticacao_completa(tracker)
        if not autenticado:
            dispatcher.utter_message(text="Por favor, faca a autenticacao primeiro. Envie uma saudacao para comecar.")
            logger.warning(f"[{self.name()}] Tentativa de buscar info atividade sem autenticacao valida")
            return eventos_inatividade
        
        pergunta_aluno = tracker.latest_message.get('text')
        # Salvar pergunta do aluno
        salvar_pergunta_aluno(pergunta_aluno, tracker=tracker)
        
        # Enviar indicador de digitando
        chat_id = obter_chat_id_do_tracker(tracker)
        if chat_id:
            enviar_indicador_digitando(chat_id)
            manter_indicador_digitando(chat_id, duracao=20)
        
        atividade = next(tracker.get_latest_entity_values("atividade_academica"), None)
        intent = tracker.latest_message['intent'].get('name')
        pergunta_lower = pergunta_aluno.lower()
        
        # CORREÇÃO: Verificar se o aluno pediu explicitamente o documento
        # Só retornar documentos se o aluno mencionar palavras relacionadas a documento/download
        palavras_documento = ["documento", "doc", "baixar", "download", "arquivo", "pdf", "manda", "envia", "preciso do", "quero o", "quero baixar", "onde baixo", "tem algum"]
        pediu_documento = any(palavra in pergunta_lower for palavra in palavras_documento)
        
        # CORREÇÃO: Melhorar detecção de atividade acadêmica
        if not atividade:
            if "tcc" in pergunta_lower or "trabalho de conclusao" in pergunta_lower or "trabalho de curso" in pergunta_lower or "tc2" in pergunta_lower or "tc 2" in pergunta_lower:
                atividade = "Trabalho de Curso II"
            elif "aps" in pergunta_lower or "atividade pratica" in pergunta_lower:
                atividade = "APS"
            elif "estagio" in pergunta_lower or "estágio" in pergunta_lower:
                atividade = "Estagio"
            elif "horas complementares" in pergunta_lower:
                atividade = "Horas Complementares"
            elif "tcc" in intent:
                atividade = "TCC"
            elif "aps" in intent:
                atividade = "APS"
            elif "estagio" in intent:
                atividade = "Estagio"
            elif "horas_complementares" in intent:
                atividade = "Horas Complementares"
        
        if not atividade:
            dispatcher.utter_message(text="Sobre qual atividade voce quer saber? (TCC, APS, Estagio, Horas Complementares)")
            return []

        logger.info(f"[{self.name()}] Buscando informacoes sobre atividade: {atividade}")
        dispatcher.utter_message(text=f"Buscando informacoes sobre {atividade}...")
        
        try:
            # CORREÇÃO: Mapear atividade para tipo_trabalho na tabela
            tipo_trabalho_busca = None
            if atividade in ["Trabalho de Curso II", "TCC", "TC2"]:
                tipo_trabalho_busca = "TC 2"
            elif atividade == "APS":
                tipo_trabalho_busca = "APS"
            elif atividade in ["Estagio", "Estágio"]:
                tipo_trabalho_busca = "estagio"
            elif atividade == "Horas Complementares":
                tipo_trabalho_busca = "horas_complementares"
            
            trabalhos_encontrados = []
            info_principal = None
            
            # PRIORIDADE 1: Buscar na tabela trabalho_academico (fonte principal)
            if tipo_trabalho_busca:
                try:
                    # Buscar informações do aluno para obter curso
                    autenticado = tracker.get_slot("autenticado")
                    access_token = tracker.get_slot("access_token")
                    
                    if autenticado and access_token:
                        headers = get_auth_headers(tracker, verificar_validade=True)
                        if "Authorization" not in headers:
                            logger.warning(f"[{self.name()}] Token invalido ao buscar aluno autenticado")
                        else:
                            response_aluno = requests.get(
                                f"{API_URL}/alunos/get_aluno_autenticado/",
                                headers=headers,
                                timeout=10
                            )
                        if response_aluno.ok:
                            aluno_data = response_aluno.json()
                            id_curso = aluno_data.get('id_curso')
                            if id_curso:
                                # CORREÇÃO: Usar endpoint específico que já filtra por tipo
                                tipo_encoded = quote(tipo_trabalho_busca, safe='')
                                response_trabalhos = requests.get(
                                    f"{API_URL}/trabalho_academico/curso/{id_curso}/tipo/{tipo_encoded}",
                                    timeout=10
                                )
                                if response_trabalhos.ok:
                                    trabalhos = ResponseValidator.validate_list_response(response_trabalhos)
                                    trabalhos_encontrados = trabalhos if trabalhos else []
                                    logger.info(f"[{self.name()}] {len(trabalhos_encontrados)} trabalho(s) encontrado(s) via endpoint específico")
                                else:
                                    logger.debug(f"[{self.name()}] Endpoint específico retornou erro, tentando endpoint genérico")
                                    # Fallback: buscar todos e filtrar manualmente
                                    headers = get_auth_headers(tracker, verificar_validade=True)
                                    response_trabalhos = requests.get(
                                        f"{API_URL}/trabalho_academico/curso/{id_curso}",
                                        headers=headers,
                                        timeout=10
                                    )
                                    if response_trabalhos.ok:
                                        trabalhos = ResponseValidator.validate_list_response(response_trabalhos)
                                        for trabalho in trabalhos:
                                            if isinstance(trabalho, dict):
                                                tipo_trabalho = trabalho.get('tipo', trabalho.get('tipo_trabalho', '')).strip()
                                                if tipo_trabalho.upper() == tipo_trabalho_busca.upper():
                                                    trabalhos_encontrados.append(trabalho)
                    else:
                        logger.info(f"[{self.name()}] Usuario nao autenticado, buscando apenas na base de conhecimento")
                except Exception as e:
                    logger.debug(f"[{self.name()}] Erro ao buscar trabalhos acadêmicos: {e}")
            
            # Se encontrou trabalhos na tabela, formatar informações
            if trabalhos_encontrados:
                mensagem = f"Informacoes sobre {atividade}:\n\n"
                
                # Agrupar informações gerais (se houver campos comuns)
                regras_gerais = set()
                max_integrantes = None
                temas = []
                datas_entrega = []
                
                for trabalho in trabalhos_encontrados:
                    # Coletar regras (remover duplicatas)
                    if trabalho.get('regras'):
                        regras_gerais.add(trabalho.get('regras'))
                    
                    # Coletar máximo de integrantes (pegar o primeiro encontrado)
                    if not max_integrantes and trabalho.get('maximo_integrantes'):
                        max_integrantes = trabalho.get('maximo_integrantes')
                    
                    # Coletar temas
                    if trabalho.get('tema'):
                        temas.append(trabalho.get('tema'))
                    
                    # Coletar datas de entrega
                    if trabalho.get('data_entrega'):
                        data_ent = trabalho.get('data_entrega')
                        data_fmt = data_ent.split('T')[0] if 'T' in data_ent else data_ent
                        datas_entrega.append(data_fmt)
                
                # Adicionar informações gerais
                if max_integrantes:
                    mensagem += f"Quantidade maxima de integrantes: {max_integrantes}\n\n"
                
                if regras_gerais:
                    mensagem += f"Regras:\n"
                    for regra in regras_gerais:
                        mensagem += f"{regra}\n"
                    mensagem += "\n"
                
                # Adicionar temas (se houver múltiplos)
                if temas:
                    mensagem += f"Temas:\n"
                    for tema in temas[:5]:  # Limitar a 5 temas
                        mensagem += f"- {tema}\n"
                    mensagem += "\n"
                
                # Adicionar datas de entrega
                if datas_entrega:
                    mensagem += f"Datas de entrega:\n"
                    for data_ent in sorted(set(datas_entrega))[:5]:  # Limitar a 5 datas, ordenadas
                        mensagem += f"- {data_ent}\n"
                
                dispatcher.utter_message(text=mensagem.strip())
                logger.info(f"[{self.name()}] {len(trabalhos_encontrados)} trabalho(s) encontrado(s) na tabela trabalho_academico para '{atividade}'")
                return []
            
            # PRIORIDADE 2: Se não encontrou na tabela, buscar na base de conhecimento
            termos_busca = [atividade]
            if atividade == "Trabalho de Curso II":
                termos_busca.extend(["TC2", "TC 2", "Trabalho de Curso", "TCC"])
            elif atividade == "APS":
                termos_busca.extend(["Atividades Práticas Supervisionadas", "Atividade Pratica Supervisionada"])
            
            contextos_encontrados = []
            documentos_encontrados = []  # Lista de URLs de documentos encontrados
            
            # Mapear atividade para o campo ID correspondente na base de conhecimento
            campo_id_atividade = None
            if atividade in ["Trabalho de Curso II", "TCC", "TC2"]:
                campo_id_atividade = "id_tcc"
            elif atividade == "APS":
                campo_id_atividade = "id_aps"
            elif atividade in ["Estagio", "Estágio"]:
                campo_id_atividade = "id_estagio"
            elif atividade == "Horas Complementares":
                campo_id_atividade = "id_hora_complementares"
            
            # CORREÇÃO: Buscar documentos SOMENTE se o aluno pediu explicitamente
            # Primeiro, buscar documentos diretamente na base de conhecimento
            # Buscar todos os documentos e filtrar pelos IDs relacionados à atividade
            if campo_id_atividade and pediu_documento:
                try:
                    # CORREÇÃO: O endpoint requer min_length=3, então não podemos fazer busca vazia
                    # Vamos buscar usando o termo da atividade
                    termo_busca = atividade if len(atividade) >= 3 else f"{atividade} trabalho academico"
                    headers = get_auth_headers(tracker, verificar_validade=True)
                    response_docs = requests.get(
                        f"{API_URL}/baseconhecimento/get_buscar",
                        params={"q": termo_busca},
                        headers=headers,
                        timeout=10
                    )
                    
                    if response_docs.ok:
                        dados_docs = ResponseValidator.validate_json_response(response_docs)
                        if dados_docs:
                            # Processar diferentes formatos de resposta
                            items_para_verificar = []
                            
                            if isinstance(dados_docs, list):
                                items_para_verificar = dados_docs
                            elif isinstance(dados_docs, dict):
                                # Tentar diferentes campos possíveis
                                items_para_verificar = dados_docs.get("documentos", [])
                                if not items_para_verificar:
                                    items_para_verificar = dados_docs.get("items", [])
                                if not items_para_verificar and isinstance(dados_docs.get("data"), list):
                                    items_para_verificar = dados_docs.get("data", [])
                            
                            # Filtrar documentos relacionados à atividade
                            for item in items_para_verificar:
                                if isinstance(item, dict):
                                    # Verificar se o documento tem o ID da atividade preenchido
                                    if item.get(campo_id_atividade):
                                        url_doc = item.get('url_documento')
                                        if url_doc and url_doc.strip() and url_doc not in documentos_encontrados:
                                            documentos_encontrados.append(url_doc)
                                            logger.info(f"[{self.name()}] Documento encontrado para {atividade}: {url_doc}")
                except Exception as e:
                    logger.debug(f"[{self.name()}] Erro ao buscar documentos completos: {e}")
            
            # Buscar contextos e verificar se há mais documentos nas respostas de busca
            for termo in termos_busca:
                try:
                    headers = get_auth_headers(tracker, verificar_validade=True)
                    response = requests.get(f"{API_URL}/baseconhecimento/get_buscar", params={"q": termo}, headers=headers, timeout=10)
                    if response.ok:
                        dados = ResponseValidator.validate_json_response(response)
                        if dados:
                            # Extrair contextos
                            contextos = dados.get("contextos", [])
                            if contextos and isinstance(contextos, list):
                                contextos_encontrados.extend(contextos)
                                logger.debug(f"[{self.name()}] Encontrados {len(contextos)} contexto(s) para termo '{termo}'")
                            
                            # Verificar se a resposta contém documentos completos
                            if isinstance(dados, list):
                                for item in dados:
                                    if isinstance(item, dict):
                                        # Verificar se o item está relacionado à atividade
                                        if campo_id_atividade and item.get(campo_id_atividade):
                                            url_doc = item.get('url_documento')
                                            if url_doc and url_doc.strip() and url_doc not in documentos_encontrados:
                                                documentos_encontrados.append(url_doc)
                                                logger.info(f"[{self.name()}] Documento encontrado na busca por termo '{termo}': {url_doc}")
                            elif isinstance(dados, dict):
                                # Verificar campos de documentos
                                docs_list = dados.get("documentos", [])
                                if not docs_list:
                                    docs_list = dados.get("items", [])
                                if not docs_list and dados.get(campo_id_atividade):
                                    # Se o próprio objeto tem o ID, pode ser um documento
                                    url_doc = dados.get('url_documento')
                                    if url_doc and url_doc.strip() and url_doc not in documentos_encontrados:
                                        documentos_encontrados.append(url_doc)
                                        logger.info(f"[{self.name()}] Documento encontrado no objeto principal: {url_doc}")
                                
                                # Verificar lista de documentos
                                for doc in docs_list:
                                    if isinstance(doc, dict) and campo_id_atividade and doc.get(campo_id_atividade):
                                        url_doc = doc.get('url_documento')
                                        if url_doc and url_doc.strip() and url_doc not in documentos_encontrados:
                                            documentos_encontrados.append(url_doc)
                                            logger.info(f"[{self.name()}] Documento encontrado na lista: {url_doc}")
                            

                except Exception as e:
                    logger.debug(f"[{self.name()}] Erro ao buscar com termo '{termo}': {e}")
                    continue
            
            # CORREÇÃO: Se ainda não encontrou documentos, tentar buscar usando endpoint específico
            # Tentar usar get_baseconhecimento_url_documento/{termo} para buscar URLs diretamente
            # Só buscar se o aluno pediu documento
            if not documentos_encontrados and campo_id_atividade and pediu_documento:
                try:
                    termos_especificos = []
                    if atividade in ["Trabalho de Curso II", "TCC", "TC2"]:
                        termos_especificos = ["TCC", "TC2", "Trabalho de Curso"]
                    elif atividade == "APS":
                        termos_especificos = ["APS", "Atividade Prática"]
                    elif atividade in ["Estagio", "Estágio"]:
                        termos_especificos = ["Estágio", "Estagio"]
                    elif atividade == "Horas Complementares":
                        termos_especificos = ["Horas Complementares"]
                    
                    for termo_esp in termos_especificos[:2]:  # Limitar a 2 termos
                        try:
                            # Tentar endpoint get_baseconhecimento_url_documento
                            termo_codificado = quote(termo_esp, safe='')
                            headers = get_auth_headers(tracker, verificar_validade=True)
                            response_url = requests.get(
                                f"{API_URL}/baseconhecimento/get_baseconhecimento_url_documento/{termo_codificado}",
                                headers=headers,
                                timeout=10
                            )
                            if response_url.ok:
                                dados_url = ResponseValidator.validate_json_response(response_url)
                                if dados_url:
                                    # O endpoint pode retornar URL diretamente ou um objeto com URL
                                    url_doc = None
                                    if isinstance(dados_url, str):
                                        url_doc = dados_url
                                    elif isinstance(dados_url, dict):
                                        url_doc = dados_url.get('url_documento') or dados_url.get('url') or dados_url.get('url_documento_origem')
                                        # Verificar se o documento está relacionado à atividade
                                        if url_doc and not dados_url.get(campo_id_atividade):
                                            url_doc = None  # Não está relacionado
                                    elif isinstance(dados_url, list):
                                        for item in dados_url:
                                            if isinstance(item, dict) and item.get(campo_id_atividade):
                                                url_doc = item.get('url_documento')
                                                if url_doc and url_doc.strip() and url_doc not in documentos_encontrados:
                                                    documentos_encontrados.append(url_doc)
                                                    logger.info(f"[{self.name()}] Documento encontrado via get_baseconhecimento_url_documento '{termo_esp}': {url_doc}")
                                                url_doc = None  # Já processado
                                    
                                    if url_doc and url_doc.strip() and url_doc not in documentos_encontrados:
                                        documentos_encontrados.append(url_doc)
                                        logger.info(f"[{self.name()}] Documento encontrado via get_baseconhecimento_url_documento '{termo_esp}': {url_doc}")
                            
                            # Também tentar get_buscar com termo específico
                            response_esp = requests.get(
                                f"{API_URL}/baseconhecimento/get_buscar",
                                params={"q": termo_esp},
                                timeout=10
                            )
                            if response_esp.ok:
                                dados_esp = ResponseValidator.validate_json_response(response_esp)
                                if dados_esp:
                                    # Processar resposta
                                    items_esp = []
                                    if isinstance(dados_esp, list):
                                        items_esp = dados_esp
                                    elif isinstance(dados_esp, dict):
                                        items_esp = dados_esp.get("documentos", []) or dados_esp.get("items", [])
                                        if not items_esp and dados_esp.get(campo_id_atividade):
                                            items_esp = [dados_esp]
                                    
                                    for item in items_esp:
                                        if isinstance(item, dict) and item.get(campo_id_atividade):
                                            url_doc = item.get('url_documento')
                                            if url_doc and url_doc.strip() and url_doc not in documentos_encontrados:
                                                documentos_encontrados.append(url_doc)
                                                logger.info(f"[{self.name()}] Documento encontrado via get_buscar com termo '{termo_esp}': {url_doc}")
                        except Exception as e:
                            logger.debug(f"[{self.name()}] Erro ao buscar com termo específico '{termo_esp}': {e}")
                            continue
                except Exception as e:
                    logger.debug(f"[{self.name()}] Erro ao buscar documentos por ID: {e}")
            
            if contextos_encontrados or documentos_encontrados:
                # Remover duplicatas mantendo ordem
                contextos_unicos = []
                for ctx in contextos_encontrados:
                    if ctx not in contextos_unicos:
                        contextos_unicos.append(ctx)
                

                # Combinar contextos e documentos de forma mais legível
                mensagem = f"Informacoes sobre {atividade}:\n\n"
                
                # Adicionar contextos (se houver)
                if contextos_unicos:
                    for i, contexto in enumerate(contextos_unicos[:3], 1):  # Limitar a 3 contextos
                        mensagem += f"{contexto}\n\n"
                
                # Adicionar documentos (URLs) se encontrados E se o aluno pediu explicitamente
                if documentos_encontrados and pediu_documento:
                    mensagem += f"📄 Documentos disponiveis para download:\n"
                    for i, url_doc in enumerate(documentos_encontrados, 1):
                        mensagem += f"{i}. {url_doc}\n"
                    mensagem += "\n"
                elif documentos_encontrados and not pediu_documento:
                    # Se encontrou documentos mas o aluno não pediu, não mostrar
                    logger.info(f"[{self.name()}] Documentos encontrados mas aluno nao pediu explicitamente. Nao exibindo URLs.")
                
                dispatcher.utter_message(text=mensagem.strip())

                logger.info(f"[{self.name()}] {len(contextos_unicos)} informacao(oes) e {len(documentos_encontrados)} documento(s) encontrado(s) para '{atividade}'")
            else:
                dispatcher.utter_message(text=f"Nao encontrei informacoes detalhadas sobre {atividade} no momento.")
                logger.info(f"[{self.name()}] Nenhuma informacao encontrada para '{atividade}'")
                
        except Exception as e:
            ErrorHandler.handle_api_error(
                dispatcher, e,
                context=f"Buscar informacoes sobre atividade - {atividade}",
                action_name=self.name()
            )
        return []

### CLASSE PARA BUSCAR ATENDIMENTO DOCENTE ###
class ActionBuscarAtendimentoDocente(Action):
    def name(self) -> Text:
        return "action_buscar_atendimento_docente"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        # PRIMEIRO: Verificar inatividade (pode deslogar se inativo)
        ainda_autenticado, eventos_inatividade = verificar_e_atualizar_inatividade(tracker, dispatcher)
        if not ainda_autenticado:
            return eventos_inatividade
        
        # SEGUNDO: Verificar autenticação completa
        autenticado, access_token = verificar_autenticacao_completa(tracker)
        if not autenticado:
            dispatcher.utter_message(text="Por favor, faca a autenticacao primeiro. Envie uma saudacao para comecar.")
            logger.warning(f"[{self.name()}] Tentativa de buscar atendimento docente sem autenticacao valida")
            return eventos_inatividade
        
        pergunta_aluno = tracker.latest_message.get('text')
        # Salvar pergunta do aluno
        salvar_pergunta_aluno(pergunta_aluno, tracker=tracker)
        
        # Enviar indicador de digitando
        chat_id = obter_chat_id_do_tracker(tracker)
        if chat_id:
            enviar_indicador_digitando(chat_id)
        
        # CORREÇÃO: Tentar extrair nome do docente da entidade primeiro
        nome_docente = next(tracker.get_latest_entity_values("nome_docente"), None)
        
        # CORREÇÃO: Se ainda não encontrou, tentar extrair do texto ANTES de usar o slot
        # Isso evita usar valores antigos do slot quando há uma nova pergunta
        if not nome_docente:
            pergunta_lower = pergunta_aluno.lower()
            # Verificar se há menção a professores conhecidos (buscar palavras-chave)
            # Mapear palavras-chave para nomes completos
            professores_map = {
                "alvaro": "Álvaro",
                "álvaro": "Álvaro",
                "eliane": "Eliane",
                "myriam": "Miryam",
                "miryam": "Miryam",
                "magrini": "Magrini",
                "luiz": "Luiz",
                "hugo": "Hugo",
                "arthur": "Arthur"
            }
            
            # Buscar por palavras-chave no texto
            for palavra_chave, nome_completo in professores_map.items():
                if palavra_chave in pergunta_lower:
                    # Se encontrar "luiz" e "magrini" juntos, usar "Luiz Magrini"
                    if palavra_chave == "luiz" and "magrini" in pergunta_lower:
                        nome_docente = "Luiz Magrini"
                    elif palavra_chave == "magrini" and "luiz" in pergunta_lower:
                        nome_docente = "Luiz Magrini"
                    else:
                        nome_docente = nome_completo
                    logger.info(f"[{self.name()}] Nome extraido do texto: '{nome_docente}'")
                    break
        
        # CORREÇÃO: Só usar o slot se não encontrou nem na entidade nem no texto
        # Isso evita usar valores antigos do slot quando há uma nova pergunta
        if not nome_docente:
            nome_docente = tracker.get_slot("nome_docente")
            # Se o slot tem um valor, verificar se ele está presente na pergunta atual
            # Se não estiver, limpar o slot para evitar confusão
            if nome_docente:
                pergunta_lower = pergunta_aluno.lower()
                nome_docente_lower = nome_docente.lower()
                # Se o nome do slot não está na pergunta atual, não usar o slot
                if nome_docente_lower not in pergunta_lower:
                    logger.info(f"[{self.name()}] Slot contem '{nome_docente}' mas nao esta na pergunta atual. Ignorando slot.")
                    nome_docente = None
        
        if not nome_docente:

            dispatcher.utter_message(text="De qual professor ou coordenador voce quer o horario de atendimento?")
            return [SlotSet("nome_docente", None)]

        logger.info(f"[{self.name()}] Buscando atendimento do docente: {nome_docente}")
        
        try:
            # CORREÇÃO: Usar endpoint específico para buscar por nome (mais eficiente)
            # Tentar múltiplas variações do nome para melhorar a busca
            variacoes_nome = [nome_docente]
            
            # Adicionar variações comuns
            nome_lower = nome_docente.lower()
            if "luiz" in nome_lower and "magrini" in nome_lower:
                variacoes_nome.extend(["Luiz Magrini", "Magrini", "Luiz"])
            elif "magrini" in nome_lower:
                variacoes_nome.extend(["Magrini", "Luiz Magrini", "Luiz"])
            elif "alvaro" in nome_lower or "álvaro" in nome_lower:
                variacoes_nome.extend(["Álvaro", "Alvaro", "Álvaro Prado", "Prado"])
            elif "myriam" in nome_lower or "miryam" in nome_lower:
                variacoes_nome.extend(["Miryam", "Myriam", "Miryam Moraes", "Moraes"])
            elif "eliane" in nome_lower:
                variacoes_nome.extend(["Eliane", "Eliane Santiago", "Santiago"])
            elif "hugo" in nome_lower:
                variacoes_nome.extend(["Hugo", "Hugo Insua", "Insua"])
            elif "arthur" in nome_lower:
                variacoes_nome.extend(["Arthur", "Arthur Battaglia", "Battaglia"])
            
            # Remover duplicatas mantendo ordem
            variacoes_nome = list(dict.fromkeys(variacoes_nome))
            
            encontrado = None
            
            # Tentar buscar primeiro em professores com todas as variações
            for variacao in variacoes_nome:
                if encontrado:
                    break
                try:
                    nome_encoded = quote(variacao, safe='')
                    headers = get_auth_headers(tracker, verificar_validade=True)
                    response_prof = requests.get(
                        f"{API_URL}/professores/get_nome/{nome_encoded}",
                        headers=headers,
                        timeout=10
                    )
                    if response_prof.ok:
                        professores = ResponseValidator.validate_list_response(response_prof)
                        if professores and len(professores) > 0:
                            # Pegar o primeiro resultado
                            encontrado = professores[0]
                            logger.info(f"[{self.name()}] Professor encontrado via endpoint com variacao '{variacao}': '{nome_docente}'")
                            break
                except requests.exceptions.HTTPError as e:
                    if e.response.status_code != 404:
                        logger.debug(f"[{self.name()}] Erro ao buscar professor com variacao '{variacao}': {e}")
                except Exception as e:
                    logger.debug(f"[{self.name()}] Erro ao buscar professor com variacao '{variacao}': {e}")
            
            # Se não encontrou em professores, tentar em coordenadores
            if not encontrado:
                for variacao in variacoes_nome:
                    if encontrado:
                        break
                    try:
                        nome_encoded = quote(variacao, safe='')
                        headers = get_auth_headers(tracker, verificar_validade=True)
                        response_coord = requests.get(
                            f"{API_URL}/coordenador/get_nome/{nome_encoded}",
                            headers=headers,
                            timeout=10
                        )
                        if response_coord.ok:
                            coordenadores = ResponseValidator.validate_list_response(response_coord)
                            if coordenadores and len(coordenadores) > 0:
                                encontrado = coordenadores[0]
                                logger.info(f"[{self.name()}] Coordenador encontrado via endpoint com variacao '{variacao}': '{nome_docente}'")
                                break
                    except requests.exceptions.HTTPError as e:
                        if e.response.status_code != 404:
                            logger.debug(f"[{self.name()}] Erro ao buscar coordenador com variacao '{variacao}': {e}")
                    except Exception as e:
                        logger.debug(f"[{self.name()}] Erro ao buscar coordenador com variacao '{variacao}': {e}")
            
            if encontrado:
                nome = encontrado.get('nome_professor') or encontrado.get('nome_coordenador')
                sobrenome = encontrado.get('sobrenome_professor') or encontrado.get('sobrenome_coordenador')
                nome_completo = f"{nome} {sobrenome}".strip() if sobrenome else nome
                tipo_docente = encontrado.get('tipo', 'docente')
                
                # Construir mensagem de atendimento
                mensagem = f"Atendimento {nome_completo}:\n"
                
                # Adicionar informações específicas do tipo
                if tipo_docente == 'professor':
                    # Disciplinas do professor - pode vir como array ou None
                    disciplina_nomes = encontrado.get('disciplina_nomes')
                    if disciplina_nomes and isinstance(disciplina_nomes, list) and len(disciplina_nomes) > 0:
                        # Filtrar valores None ou vazios
                        disciplinas_validas = [d for d in disciplina_nomes if d and str(d).strip()]
                        if disciplinas_validas:
                            mensagem += f"Disciplinas: {', '.join(disciplinas_validas)}\n"
                elif tipo_docente == 'coordenador':
                    # Departamento e cursos do coordenador
                    departamento = encontrado.get('departamento')
                    if departamento and str(departamento).strip():
                        mensagem += f"Departamento: {departamento}\n"
                    curso_nomes = encontrado.get('curso_nomes')
                    if curso_nomes and isinstance(curso_nomes, list) and len(curso_nomes) > 0:
                        # Filtrar valores None ou vazios
                        cursos_validos = [c for c in curso_nomes if c and str(c).strip()]
                        if cursos_validos:
                            mensagem += f"Cursos: {', '.join(cursos_validos)}\n"
                
                # Dias de atendimento
                dias_atendimento = encontrado.get('dias_atendimento')
                if dias_atendimento and isinstance(dias_atendimento, list) and len(dias_atendimento) > 0:
                    # Filtrar valores None ou vazios
                    dias_validos = [d for d in dias_atendimento if d and str(d).strip()]
                    if dias_validos:
                        mensagem += f"Dias: {', '.join(dias_validos)}\n"
                    else:
                        mensagem += "Dias: Nao informado\n"
                else:
                    mensagem += "Dias: Nao informado\n"
                
                # Horários de atendimento
                hora_inicio = encontrado.get('atendimento_hora_inicio')
                hora_fim = encontrado.get('atendimento_hora_fim')
                
                if hora_inicio and hora_fim:
                    # Formatar horário (pode vir como string, time object ou None)
                    try:
                        if isinstance(hora_inicio, str):
                            # Se for string, pode vir como "HH:MM:SS" ou "HH:MM"
                            hora_inicio_str = hora_inicio[:5] if len(hora_inicio) >= 5 else hora_inicio
                        else:
                            # Se for time object, converter para string
                            hora_inicio_str = str(hora_inicio)[:5] if hora_inicio else "00:00"
                        
                        if isinstance(hora_fim, str):
                            hora_fim_str = hora_fim[:5] if len(hora_fim) >= 5 else hora_fim
                        else:
                            hora_fim_str = str(hora_fim)[:5] if hora_fim else "00:00"
                        
                        mensagem += f"Horario: {hora_inicio_str} as {hora_fim_str}"
                    except Exception as e:
                        logger.warning(f"[{self.name()}] Erro ao formatar horario: {e}")
                        mensagem += "Horario: Nao informado"
                else:
                    mensagem += "Horario: Nao informado"
                
                dispatcher.utter_message(text=mensagem)
                logger.info(f"[{self.name()}] Atendimento encontrado para '{nome_completo}' ({tipo_docente})")
                # Limpar o slot para evitar usar valores antigos em próximas consultas
                return [SlotSet("nome_docente", None)]
            else:
                # CORREÇÃO: Verificar se o nome usado corresponde à pergunta atual
                # Se não corresponder, informar que não foi possível identificar o nome
                pergunta_lower = pergunta_aluno.lower()
                nome_docente_lower = nome_docente.lower()
                
                if nome_docente_lower not in pergunta_lower:
                    dispatcher.utter_message(text=f"Nao foi possivel identificar o nome do professor ou coordenador na sua pergunta. Por favor, informe o nome completo.")
                else:
                    dispatcher.utter_message(text=f"Professor(a) ou coordenador(a) '{nome_docente}' nao encontrado(a). Verifique se o nome esta correto.")
                
                logger.warning(f"[{self.name()}] Docente '{nome_docente}' nao encontrado")
                # Limpar o slot para evitar usar valores antigos em próximas consultas
                return [SlotSet("nome_docente", None)]

        except Exception as e:
            ErrorHandler.handle_api_error(
                dispatcher, e,
                context=f"Buscar atendimento docente - {nome_docente}",
                action_name=self.name()
            )
            
        return [SlotSet("nome_docente", None)] # Limpa o slot

### CLASSE PARA BUSCAR MATERIAL DE DISCIPLINA ###
class ActionBuscarMaterial(Action):
    def name(self) -> Text:
        return "action_buscar_material"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        # PRIMEIRO: Verificar inatividade (pode deslogar se inativo)
        ainda_autenticado, eventos_inatividade = verificar_e_atualizar_inatividade(tracker, dispatcher)
        if not ainda_autenticado:
            return eventos_inatividade
        
        # SEGUNDO: Verificar autenticação completa
        autenticado, access_token = verificar_autenticacao_completa(tracker)
        if not autenticado:
            dispatcher.utter_message(text="Por favor, faca a autenticacao primeiro. Envie uma saudacao para comecar.")
            logger.warning(f"[{self.name()}] Tentativa de buscar material sem autenticacao valida")
            return eventos_inatividade
        
        pergunta_aluno = tracker.latest_message.get('text')
        # Salvar pergunta do aluno
        salvar_pergunta_aluno(pergunta_aluno, tracker=tracker)
        
        # O formulario garante que o slot 'disciplina' esta preenchido
        disciplina_nome = tracker.get_slot("disciplina")
        
        if not disciplina_nome:
            # Isso nao deve acontecer se o form estiver certo
            dispatcher.utter_message(text="Claro. De qual disciplina voce quer o material?")
            return []
        
        # Enviar indicador de digitando
        chat_id = obter_chat_id_do_tracker(tracker)
        if chat_id:
            enviar_indicador_digitando(chat_id)
            manter_indicador_digitando(chat_id, duracao=20)
        
        logger.info(f"[{self.name()}] Buscando materiais para disciplina: {disciplina_nome}")
        dispatcher.utter_message(text=f"Buscando materiais para {disciplina_nome}...")
        
        try:
            # SOLUÇÃO: Usar endpoint de busca de base de conhecimento e buscar URLs relacionadas
            # Primeiro verificar se há conteúdo relacionado
            headers = get_auth_headers(tracker, verificar_validade=True)
            if "Authorization" not in headers:
                dispatcher.utter_message(text="Sessao expirada. Por favor, faca a autenticacao novamente enviando uma saudacao.")
                logger.error(f"[{self.name()}] Token de autenticacao nao disponivel ou invalido")
                return []
            
            response = requests.get(
                f"{API_URL}/baseconhecimento/get_buscar",
                params={"q": disciplina_nome},
                headers=headers,
                timeout=10
            )
            
            contextos_encontrados = 0
            if response.ok:
                dados = ResponseValidator.validate_json_response(response)
                if dados:
                    contextos = dados.get("contextos", [])
                    contextos_encontrados = len(contextos) if contextos else 0
            
            # Buscar URLs de documentos relacionados
            urls_documentos = buscar_urls_documentos_relacionados(disciplina_nome, limite=5, headers=headers)
            
            if contextos_encontrados > 0 or urls_documentos:
                mensagem = f"Encontrei material para {disciplina_nome}:\n\n"
                
                if urls_documentos:
                    mensagem += f"Documentos disponiveis:\n"
                    for i, url in enumerate(urls_documentos, 1):
                        mensagem += f"{i}. {url}\n"
                    
                    if contextos_encontrados > 0:
                        mensagem += f"\nConteudo processado encontrado: {contextos_encontrados} trecho(s) de material."
                else:
                    mensagem += f"Conteudo processado encontrado: {contextos_encontrados} trecho(s) de material."
                    mensagem += "\n\n(Nao ha documentos com URL disponivel no momento.)"
                
                dispatcher.utter_message(text=mensagem)
                logger.info(f"[{self.name()}] {len(urls_documentos)} documento(s) e {contextos_encontrados} contexto(s) encontrado(s) para '{disciplina_nome}'")
            else:
                # Nenhum material encontrado
                dispatcher.utter_message(text=f"Nao encontrei material disponivel para {disciplina_nome} no momento.")
                logger.info(f"[{self.name()}] Nenhum material encontrado para '{disciplina_nome}'")
                return [SlotSet("disciplina", None)]
                
        except Exception as e:
            ErrorHandler.handle_api_error(
                dispatcher, e,
                context=f"Buscar material - disciplina {disciplina_nome}",
                action_name=self.name()
            )
            return [SlotSet("disciplina", None)]
        
        # Limpa o slot para a proxima pergunta
        return [SlotSet("disciplina", None)]
    
### CLASSE PARA BUSCAR EMENTA DE DISCIPLINA ###
class ActionBuscarEmenta(Action):
    def name(self) -> Text:
        return "action_buscar_ementa"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        # PRIMEIRO: Verificar inatividade (pode deslogar se inativo)
        ainda_autenticado, eventos_inatividade = verificar_e_atualizar_inatividade(tracker, dispatcher)
        if not ainda_autenticado:
            return eventos_inatividade
        
        # SEGUNDO: Verificar autenticação completa
        autenticado, access_token = verificar_autenticacao_completa(tracker)
        if not autenticado:
            dispatcher.utter_message(text="Por favor, faca a autenticacao primeiro. Envie uma saudacao para comecar.")
            logger.warning(f"[{self.name()}] Tentativa de buscar ementa sem autenticacao valida")
            return eventos_inatividade
        
        pergunta_aluno = tracker.latest_message.get('text')
        # Salvar pergunta do aluno
        salvar_pergunta_aluno(pergunta_aluno, tracker=tracker)
        
        # Enviar indicador de digitando
        chat_id = obter_chat_id_do_tracker(tracker)
        if chat_id:
            enviar_indicador_digitando(chat_id)
        
        # Extrair disciplina
        disciplina_nome = next(tracker.get_latest_entity_values("disciplina"), None)
        
        # Se não encontrou disciplina, verificar slot
        if not disciplina_nome:
            disciplina_nome = tracker.get_slot("disciplina")
        
        # Se ainda não encontrou, tentar extrair manualmente
        if not disciplina_nome:
            pergunta_lower = pergunta_aluno.lower()
            palavras_remover = ["é", "de", "a", "o", "da", "do", "das", "dos", "qual", "a", "o", "ementa", "da", "disciplina", "materia", "matéria"]
            palavras = pergunta_aluno.split()
            for i, palavra in enumerate(palavras):
                palavra_limpa = palavra.lower().strip('.,!?;:')
                if palavra_limpa not in palavras_remover and len(palavra_limpa) > 2:
                    possivel_disc = ' '.join(palavras[i:i+4])
                    id_test = get_disciplina_id_by_name(possivel_disc, tracker)
                    if id_test:
                        disciplina_nome = possivel_disc
                        logger.info(f"[{self.name()}] Disciplina extraida manualmente: '{disciplina_nome}'")
                        break
        
        if not disciplina_nome:
            dispatcher.utter_message(text="De qual disciplina voce quer saber a ementa?")
            return []
        
        logger.info(f"[{self.name()}] Buscando ementa para disciplina: {disciplina_nome}")
        dispatcher.utter_message(text=f"Buscando ementa de {disciplina_nome}...")
        
        try:
            headers = get_auth_headers(tracker, verificar_validade=True)
            if "Authorization" not in headers:
                dispatcher.utter_message(text="Sessao expirada. Por favor, faca a autenticacao novamente enviando uma saudacao.")
                logger.error(f"[{self.name()}] Token de autenticacao nao disponivel ou invalido")
                return []
            
            # Codificar o nome da disciplina para URL
            nome_encoded = quote(disciplina_nome, safe='')
            response = requests.get(
                f"{API_URL}/disciplinas/get_ementa/{nome_encoded}",
                headers=headers,
                timeout=10
            )
            
            if response.status_code == 404:
                dispatcher.utter_message(text=f"Nao encontrei a ementa para a disciplina '{disciplina_nome}'. Verifique se o nome esta correto.")
                logger.warning(f"[{self.name()}] Ementa nao encontrada para disciplina: {disciplina_nome}")
                return []
            
            response.raise_for_status()
            
            dados = ResponseValidator.validate_json_response(response)
            if dados:
                ementa = dados.get('ementa', '')
                
                if ementa and ementa.strip():
                    mensagem = f"Ementa de {disciplina_nome}:\n\n{ementa}"
                    dispatcher.utter_message(text=mensagem)
                    logger.info(f"[{self.name()}] Ementa encontrada para disciplina: {disciplina_nome}")
                    # Salvar contexto
                    return [
                        SlotSet("ultima_disciplina_consultada", disciplina_nome),
                        SlotSet("ultima_consulta_tipo", "ementa")
                    ]
                else:
                    dispatcher.utter_message(text=f"A disciplina '{disciplina_nome}' nao possui ementa cadastrada no momento.")
                    logger.info(f"[{self.name()}] Ementa vazia para disciplina: {disciplina_nome}")
            else:
                dispatcher.utter_message(text=f"Nao foi possivel obter a ementa da disciplina '{disciplina_nome}'.")
                logger.warning(f"[{self.name()}] Resposta invalida da API")
                
        except Exception as e:
            ErrorHandler.handle_api_error(
                dispatcher, e,
                context=f"Buscar ementa - disciplina {disciplina_nome}",
                action_name=self.name()
            )
        
        return []

### CLASSE PARA BUSCAR INFORMAÇÕES DO DOCENTE ###
class ActionBuscarInfoDocente(Action):
    def name(self) -> Text:
        return "action_buscar_info_docente"
    
    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        # PRIMEIRO: Verificar inatividade (pode deslogar se inativo)
        ainda_autenticado, eventos_inatividade = verificar_e_atualizar_inatividade(tracker, dispatcher)
        if not ainda_autenticado:
            return eventos_inatividade
        
        # SEGUNDO: Verificar autenticação completa
        autenticado, access_token = verificar_autenticacao_completa(tracker)
        if not autenticado:
            dispatcher.utter_message(text="Por favor, faca a autenticacao primeiro. Envie uma saudacao para comecar.")
            logger.warning(f"[{self.name()}] Tentativa de buscar info docente sem autenticacao valida")
            return eventos_inatividade
        
        pergunta_aluno = tracker.latest_message.get('text')
        # Salvar pergunta do aluno
        salvar_pergunta_aluno(pergunta_aluno, tracker=tracker)
        
        # Enviar indicador de digitando
        chat_id = obter_chat_id_do_tracker(tracker)
        if chat_id:
            enviar_indicador_digitando(chat_id)
        
        nome_docente = next(tracker.get_latest_entity_values("nome_docente"), None)
        

        # CORREÇÃO: Se ainda não encontrou, tentar extrair do texto ANTES de usar o slot
        # Isso evita usar valores antigos do slot quando há uma nova pergunta
        if not nome_docente:
            pergunta_lower = pergunta_aluno.lower()
            # Verificar se há menção a professores/coordenadores conhecidos
            professores_map = {
                "alvaro": "Álvaro",
                "álvaro": "Álvaro",
                "eliane": "Eliane",
                "myriam": "Miryam",
                "miryam": "Miryam",
                "magrini": "Magrini",
                "luiz": "Luiz",
                "hugo": "Hugo",
                "arthur": "Arthur"
            }
            
            # Buscar por palavras-chave no texto
            for palavra_chave, nome_completo in professores_map.items():
                if palavra_chave in pergunta_lower:
                    # Se encontrar "luiz" e "magrini" juntos, usar "Luiz Magrini"
                    if palavra_chave == "luiz" and "magrini" in pergunta_lower:
                        nome_docente = "Luiz Magrini"
                    elif palavra_chave == "magrini" and "luiz" in pergunta_lower:
                        nome_docente = "Luiz Magrini"
                    else:
                        nome_docente = nome_completo
                    logger.info(f"[{self.name()}] Nome extraido do texto: '{nome_docente}'")
                    break
        
        # CORREÇÃO: Só usar o slot se não encontrou nem na entidade nem no texto
        # Isso evita usar valores antigos do slot quando há uma nova pergunta
        if not nome_docente:
            nome_docente = tracker.get_slot("nome_docente")
            # Se o slot tem um valor, verificar se ele está presente na pergunta atual
            # Se não estiver, limpar o slot para evitar confusão
            if nome_docente:
                pergunta_lower = pergunta_aluno.lower()
                nome_docente_lower = nome_docente.lower()
                # Se o nome do slot não está na pergunta atual, não usar o slot
                if nome_docente_lower not in pergunta_lower:
                    logger.info(f"[{self.name()}] Slot contem '{nome_docente}' mas nao esta na pergunta atual. Ignorando slot.")
                    nome_docente = None
        
        if not nome_docente:
            dispatcher.utter_message(text="Qual o nome do professor ou coordenador?")
            return [SlotSet("nome_docente", None)]

        logger.info(f"[{self.name()}] Buscando informacoes do docente: {nome_docente}")

        try:
            # CORREÇÃO: Usar endpoint específico para buscar por nome (mais eficiente)
            nome_docente_encoded = quote(nome_docente, safe='')
            encontrado = None
            
            # Tentar buscar primeiro em professores
            try:
                headers = get_auth_headers(tracker, verificar_validade=True)
                response_prof = requests.get(
                    f"{API_URL}/professores/get_nome/{nome_docente_encoded}",
                    headers=headers,
                    timeout=10
                )
                if response_prof.ok:
                    professores = ResponseValidator.validate_list_response(response_prof)
                    if professores and len(professores) > 0:
                        # Pegar o primeiro resultado
                        encontrado = professores[0]
                        logger.info(f"[{self.name()}] Professor encontrado via endpoint: '{nome_docente}'")
            except requests.exceptions.HTTPError as e:
                if e.response.status_code != 404:
                    logger.debug(f"[{self.name()}] Erro ao buscar professor: {e}")
            except Exception as e:
                logger.debug(f"[{self.name()}] Erro ao buscar professor: {e}")
            
            # Se não encontrou em professores, tentar em coordenadores
            if not encontrado:
                try:
                    headers = get_auth_headers(tracker, verificar_validade=True)
                    response_coord = requests.get(
                        f"{API_URL}/coordenador/get_nome/{nome_docente_encoded}",
                        headers=headers,
                        timeout=10
                    )
                    if response_coord.ok:
                        coordenadores = ResponseValidator.validate_list_response(response_coord)
                        if coordenadores and len(coordenadores) > 0:
                            encontrado = coordenadores[0]
                            logger.info(f"[{self.name()}] Coordenador encontrado via endpoint: '{nome_docente}'")
                except requests.exceptions.HTTPError as e:
                    if e.response.status_code != 404:
                        logger.debug(f"[{self.name()}] Erro ao buscar coordenador: {e}")
                except Exception as e:
                    logger.debug(f"[{self.name()}] Erro ao buscar coordenador: {e}")
            
            if encontrado:
                email = encontrado.get('email_institucional', 'Nao informado')
                nome = encontrado.get('nome_professor') or encontrado.get('nome_coordenador')
                sobrenome = encontrado.get('sobrenome_professor') or encontrado.get('sobrenome_coordenador')
                nome_completo = f"{nome} {sobrenome}".strip() if sobrenome else nome
                tipo_docente = encontrado.get('tipo', 'docente')
                
                if tipo_docente == 'coordenador':
                    dispatcher.utter_message(text=f"Contato Coordenador(a)\nNome: {nome_completo}\nEmail: {email}")
                else:
                    dispatcher.utter_message(text=f"Contato Professor(a)\nNome: {nome_completo}\nEmail: {email}")
                logger.info(f"[{self.name()}] Informacoes encontradas para '{nome_completo}' ({tipo_docente})")
                # Limpar o slot para evitar usar valores antigos em próximas consultas
                return [SlotSet("nome_docente", None)]
            else:
                # CORREÇÃO: Verificar se o nome usado corresponde à pergunta atual
                # Se não corresponder, informar que não foi possível identificar o nome
                pergunta_lower = pergunta_aluno.lower()
                nome_docente_lower = nome_docente.lower()
                
                if nome_docente_lower not in pergunta_lower:
                    dispatcher.utter_message(text=f"Nao foi possivel identificar o nome do professor ou coordenador na sua pergunta. Por favor, informe o nome completo.")
                else:
                    dispatcher.utter_message(text=f"Nao encontrei o professor(a) ou coordenador(a) '{nome_docente}' no cadastro. Verifique se o nome esta correto.")
                
                logger.warning(f"[{self.name()}] Docente '{nome_docente}' nao encontrado")
                # Limpar o slot para evitar usar valores antigos em próximas consultas
                return [SlotSet("nome_docente", None)]

        except Exception as e:
            ErrorHandler.handle_api_error(
                dispatcher, e,
                context=f"Buscar informacoes docente - {nome_docente}",
                action_name=self.name()
            )
        return []

### CLASSE PARA BUSCAR DÚVIDAS FREQUENTES ###
class ActionBuscarDuvidasFrequentes(Action):
    def name(self) -> Text:
        return "action_buscar_duvidas_frequentes"
    
    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        """
        Busca e retorna categorias de dúvidas frequentes.
        Agrupa por tipo (Institucional vs Conteúdo) e por categoria/palavras-chave.
        """
        # PRIMEIRO: Verificar inatividade (pode deslogar se inativo)
        ainda_autenticado, eventos_inatividade = verificar_e_atualizar_inatividade(tracker, dispatcher)
        if not ainda_autenticado:
            return eventos_inatividade
        
        # SEGUNDO: Verificar autenticação completa
        autenticado, access_token = verificar_autenticacao_completa(tracker)
        if not autenticado:
            dispatcher.utter_message(text="Por favor, faca a autenticacao primeiro. Envie uma saudacao para comecar.")
            logger.warning(f"[{self.name()}] Tentativa de buscar duvidas frequentes sem autenticacao valida")
            return eventos_inatividade
        
        # Enviar indicador de digitando
        chat_id = obter_chat_id_do_tracker(tracker)
        if chat_id:
            enviar_indicador_digitando(chat_id)
            manter_indicador_digitando(chat_id, duracao=20)
        
        try:
            # 1. Buscar todas as mensagens dos alunos
            headers = get_auth_headers(tracker, verificar_validade=True)
            if "Authorization" not in headers:
                dispatcher.utter_message(text="Sessao expirada. Por favor, faca a autenticacao novamente enviando uma saudacao.")
                logger.error(f"[{self.name()}] Token de autenticacao nao disponivel ou invalido")
                return []
            
            response_msg = requests.get(
                f"{API_URL}/mensagens_aluno/get_lista_msg/",
                headers=headers,
                timeout=10
            )
            
            response_msg.raise_for_status()
            
            # VALIDAÇÃO ADICIONADA
            mensagens = ResponseValidator.validate_list_response(response_msg)
            
            # 2. Agrupar perguntas por tópicos (Dúvidas Institucionais)
            topicos_institucionais = {
                "TCC": 0,
                "APS": 0,
                "Estágio": 0,
                "Horas Complementares": 0,
                "Aviso": 0,
                "Docente": 0,
                "Disciplina": 0
            }
            
            for msg in mensagens:
                topicos = msg.get('topico', [])
                for topico in topicos:
                    if topico in topicos_institucionais:
                        topicos_institucionais[topico] += 1
            
            # 3. Buscar categorias e palavras-chave da base de conhecimento (Dúvidas de Conteúdo)
            categorias_conteudo = {}
            palavras_chave_frequentes = {}
            
            # Buscar todas as mensagens classificadas como "Conteúdo"
            mensagens_conteudo = [msg for msg in mensagens if "Conteúdo" in msg.get('topico', [])]
            
            # Agrupar por palavras-chave mais frequentes nas perguntas de conteúdo
            for msg in mensagens_conteudo:
                pergunta = msg.get('primeira_pergunta', '').lower()
                
                # Extrair palavras-chave da pergunta (palavras com mais de 4 caracteres)
                palavras = [p for p in pergunta.split() if len(p) > 4]
                for palavra in palavras:
                    palavras_chave_frequentes[palavra] = palavras_chave_frequentes.get(palavra, 0) + 1
            
            # NOTA: Para agrupar por categorias da base de conhecimento (ex: "Algoritmos", "Banco de Dados"),
            # precisaríamos de um endpoint que retorne essas informações agrupadas.
            # Por enquanto, agrupamos por palavras-chave das perguntas.
            
            # 4. Montar resposta
            mensagem = "Duvidas Frequentes por Categoria:\n\n"
            
            # Dúvidas Institucionais
            duvidas_inst = {k: v for k, v in topicos_institucionais.items() if v > 0}
            if duvidas_inst:
                mensagem += "Duvidas Institucionais:\n"
                for topico, count in sorted(duvidas_inst.items(), key=lambda x: x[1], reverse=True)[:5]:
                    mensagem += f"  - {topico}: {count} pergunta(s)\n"
                mensagem += "\n"
            
            # Dúvidas de Conteúdo (palavras-chave mais frequentes)
            if palavras_chave_frequentes:
                mensagem += "Duvidas de Conteudo (Topicos mais perguntados):\n"
                for palavra, count in sorted(palavras_chave_frequentes.items(), key=lambda x: x[1], reverse=True)[:5]:
                    mensagem += f"  - {palavra.title()}: {count} pergunta(s)\n"
            
            if not duvidas_inst and not palavras_chave_frequentes:
                mensagem += "Ainda não há dúvidas frequentes registradas."
            
            dispatcher.utter_message(text=mensagem)
            logger.info(f"[{self.name()}] Duvidas frequentes retornadas: {len(duvidas_inst)} institucionais, {len(palavras_chave_frequentes)} conteudo")
            
        except Exception as e:
            ErrorHandler.handle_api_error(
                dispatcher, e,
                context="Buscar duvidas frequentes",
                action_name=self.name()
            )
        
        return []

### AÇÕES DE AUTENTICAÇÃO ###

### CLASSE PARA ENVIAR SAUDAÇÃO ###
class ActionSaudacao(Action):
    """
    Action para enviar saudação dinâmica baseada no horário e contexto da mensagem do usuário.
    """
    def name(self) -> Text:
        return "action_saudacao"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        # Obter a mensagem do usuário para verificar se ele mencionou uma saudação específica
        mensagem_usuario = tracker.latest_message.get('text', '').lower()
        
        # Determinar saudação baseada na mensagem do usuário ou no horário
        hora_atual = datetime.now().hour
        
        # Verificar se o usuário mencionou uma saudação específica
        if 'bom dia' in mensagem_usuario or 'bomdia' in mensagem_usuario:
            saudacao = "Bom dia"
        elif 'boa tarde' in mensagem_usuario or 'boatarde' in mensagem_usuario:
            saudacao = "Boa tarde"
        elif 'boa noite' in mensagem_usuario or 'boanoite' in mensagem_usuario:
            saudacao = "Boa noite"
        else:
            # Determinar saudação baseada no horário
            if 5 <= hora_atual < 12:
                saudacao = "Bom dia"
            elif 12 <= hora_atual < 18:
                saudacao = "Boa tarde"
            else:
                saudacao = "Boa noite"
        
        # Mensagem completa de saudação
        mensagem = f"{saudacao}! Sou o seu assistente academico. Para comecarmos, preciso de algumas informacoes pessoais para que voce possa ter acesso aos dados da sua turma. Informe seu email institucional."
        
        dispatcher.utter_message(text=mensagem)
        logger.info(f"[{self.name()}] Saudacao enviada: {saudacao} (hora: {hora_atual})")
        
        return []


### CLASSE PARA VERIFICAR AUTENTICAÇÃO ###
class ActionVerificarAutenticacao(Action):
    """
    Action para verificar se o usuário já está autenticado.
    Se estiver, cancela o form de autenticação e mostra mensagem de boas-vindas.
    """
    def name(self) -> Text:
        return "action_verificar_autenticacao"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        autenticado = tracker.get_slot("autenticado")
        access_token = tracker.get_slot("access_token")
        
        if autenticado and access_token:
            # Usuário já está autenticado, cancela o form e mostra mensagem
            logger.info(f"[{self.name()}] Usuario ja autenticado. Cancelando form de autenticacao.")
            # Não mostra mensagem duplicada - a saudação já foi enviada pela regra
            # Cancela o form se estiver ativo
            return [ActiveLoop(None)]
        else:
            # Usuário não está autenticado, permite que o form continue
            logger.info(f"[{self.name()}] Usuario nao autenticado. Continuando com autenticacao.")
            return []


### CLASSE PARA VERIFICAR INATIVIDADE ###
class ActionVerificarInatividade(Action):
    """
    Action para verificar se o usuário está inativo há mais de 10 minutos.
    Se estiver, desloga o usuário automaticamente.
    """
    def name(self) -> Text:
        return "action_verificar_inatividade"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        autenticado = tracker.get_slot("autenticado")
        access_token = tracker.get_slot("access_token")
        ultima_atividade_str = tracker.get_slot("ultima_atividade_timestamp")
        
        # Se não estiver autenticado, não precisa verificar inatividade
        if not autenticado or not access_token:
            return []
        
        # Se não houver timestamp, considerar como primeira interação e salvar timestamp atual
        if not ultima_atividade_str:
            timestamp_atual = datetime.now().isoformat()
            logger.info(f"[{self.name()}] Primeira interacao apos autenticacao. Salvando timestamp.")
            return [SlotSet("ultima_atividade_timestamp", timestamp_atual)]
        
        # Verificar se passou mais de 10 minutos (600 segundos)
        try:
            ultima_atividade = datetime.fromisoformat(ultima_atividade_str)
            tempo_decorrido = (datetime.now() - ultima_atividade).total_seconds()
            timeout_minutos = 2
            timeout_segundos = timeout_minutos * 60
            
            if tempo_decorrido > timeout_segundos:
                # Usuário inativo há mais de 2 minutos - deslogar
                logger.info(f"[{self.name()}] Usuario inativo por {tempo_decorrido/60:.1f} minutos. Deslogando automaticamente.")
                dispatcher.utter_message(text="Voce ficou inativo por mais de 2 minutos. Por seguranca, sua sessao foi encerrada. Por favor, faca login novamente.")
                
                # Limpar todos os slots de autenticação
                return [
                    SlotSet("autenticado", False),
                    SlotSet("access_token", None),
                    SlotSet("ultima_atividade_timestamp", None),
                    SlotSet("email_institucional", None),
                    SlotSet("matricula_ra", None),
                    SlotSet("tipo_pergunta_ra", None),
                    SlotSet("parametro_pergunta_ra", None),
                    ActiveLoop("form_autenticacao")
                ]
            else:
                # Usuário ainda ativo - atualizar timestamp
                tempo_restante = timeout_segundos - tempo_decorrido
                logger.debug(f"[{self.name()}] Usuario ativo. Tempo restante: {tempo_restante/60:.1f} minutos.")
                timestamp_atual = datetime.now().isoformat()
                return [SlotSet("ultima_atividade_timestamp", timestamp_atual)]
                
        except (ValueError, TypeError) as e:
            # Se houver erro ao processar timestamp, resetar
            logger.warning(f"[{self.name()}] Erro ao processar timestamp: {e}. Resetando timestamp.")
            timestamp_atual = datetime.now().isoformat()
            return [SlotSet("ultima_atividade_timestamp", timestamp_atual)]


### CLASSE PARA INTERCEPTAR INTENÇÕES NÃO AUTENTICADAS ###
class ActionInterceptarIntencoesNaoAutenticado(Action):
    """
    Action para interceptar todas as intenções quando o usuário não está autenticado.
    Força o usuário a fazer login antes de permitir qualquer outra ação.
    Primeiro verifica inatividade para deslogar se necessário.
    """
    def name(self) -> Text:
        return "action_interceptar_intencoes_nao_autenticado"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        # Primeiro verificar inatividade (pode deslogar o usuário)
        verificar_inatividade = ActionVerificarInatividade()
        eventos_inatividade = verificar_inatividade.run(dispatcher, tracker, domain)
        
        # Se a verificação de inatividade deslogou o usuário, retornar os eventos
        autenticado_apos_verificacao = tracker.get_slot("autenticado")
        access_token_apos_verificacao = tracker.get_slot("access_token")
        
        # Se não estiver autenticado após verificação de inatividade, forçar autenticação
        if not autenticado_apos_verificacao or not access_token_apos_verificacao:
            # Verificar se está no meio do processo de autenticação
            active_loop = tracker.active_loop.get('name') if tracker.active_loop else None
            email = tracker.get_slot("email_institucional")
            matricula_ra = tracker.get_slot("matricula_ra")
            
            # Se estiver no form de autenticação ou já tiver email/RA, não intercepta
            if active_loop == "form_autenticacao" or email or matricula_ra:
                return eventos_inatividade
            
            # Caso contrário, força autenticação
            logger.info(f"[{self.name()}] Interceptando intencao. Usuario nao autenticado. Forcando autenticacao.")
            dispatcher.utter_message(text="Voce precisa estar autenticado para usar este recurso. Por favor, informe seu email institucional.")
            eventos_inatividade.append(ActiveLoop("form_autenticacao"))
            return eventos_inatividade
        
        # Se estiver autenticado, não intercepta (permite que outras actions executem)
        return eventos_inatividade


### CLASSE PARA BUSCAR ALUNO POR EMAIL ###
class ActionBuscarAlunoPorEmail(Action):
    """
    Action para buscar aluno por email e armazenar o RA em cache.
    Esta action é chamada após o usuário informar o email.
    """
    def name(self) -> Text:
        return "action_buscar_aluno_por_email"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        email = tracker.get_slot("email_institucional")
        
        if not email:
            dispatcher.utter_message(text="Por favor, informe seu email institucional.")
            return []
        
        # SEGURANÇA: Não logar email do usuário
        logger.info(f"[{self.name()}] Buscando aluno para autenticacao")
        
        try:
            # Buscar aluno pelo email
            response = requests.get(
                f"{API_URL}/alunos/get_email/{email}",
                timeout=10
            )
            
            if response.status_code == 404:
                dispatcher.utter_message(text="Aluno nao encontrado com este email. Por favor, verifique e tente novamente.")
                logger.warning(f"[{self.name()}] Aluno nao encontrado")
                # Limpar email e reativar form para pedir novamente
                return [
                    SlotSet("email_institucional", None),
                    ActiveLoop("form_autenticacao")
                ]
            
            if response.status_code == 500:
                # Usar mensagem variada de erro 500
                mensagem_erro = ErrorHandler.get_mensagem_erro_500()
                dispatcher.utter_message(text=mensagem_erro)
                logger.error(f"[{self.name()}] Erro 500 na API ao buscar aluno por email")
                # Limpar email e reativar form para pedir novamente
                return [
                    SlotSet("email_institucional", None),
                    ActiveLoop("form_autenticacao")
                ]
            
            response.raise_for_status()
            aluno_data = response.json()
            
            # Extrair RA do aluno
            matricula_ra = aluno_data.get("matricula_ra", "")
            
            if not matricula_ra:
                dispatcher.utter_message(text="RA nao encontrado para este aluno. Por favor, entre em contato com a secretaria.")
                logger.error(f"[{self.name()}] RA nao encontrado para aluno")
                # Limpar email e reativar form para pedir novamente
                return [
                    SlotSet("email_institucional", None),
                    ActiveLoop("form_autenticacao")
                ]
            
            # SEGURANÇA: Não logar informações sensíveis (RA completo)
            logger.info(f"[{self.name()}] Aluno encontrado para autenticacao")
            
            # Armazenar RA no slot (mas não expor para o usuário)
            # NOTA: Estes slots serão limpos após autenticação bem-sucedida
            return [
                SlotSet("matricula_ra", matricula_ra),
                SlotSet("email_institucional", email)
            ]
            
        except requests.exceptions.RequestException as e:
            ErrorHandler.handle_api_error(
                dispatcher, e,
                context="Buscar aluno por email",
                action_name=self.name()
            )
            # Limpar email e reativar form para pedir novamente
            return [
                SlotSet("email_institucional", None),
                ActiveLoop("form_autenticacao")
            ]
        except Exception as e:
            logger.error(f"[{self.name()}] Erro inesperado: {e}")
            dispatcher.utter_message(text="Ocorreu um erro ao buscar seus dados. Por favor, informe seu email novamente.")
            # Limpar email e reativar form para pedir novamente
            return [
                SlotSet("email_institucional", None),
                ActiveLoop("form_autenticacao")
            ]


### CLASSE PARA AUTENTICAR CHATBOT ###
class ActionAutenticarChatbot(Action):
    """
    Action para autenticar o usuário via chatbot usando validação parcial do RA.
    Esta action é chamada após o usuário informar a resposta sobre o RA.
    Suporta diferentes tipos de pergunta: primeiros, últimos, posição específica e completo.
    """
    def name(self) -> Text:
        return "action_autenticar_chatbot"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        email = tracker.get_slot("email_institucional")
        matricula_ra = tracker.get_slot("matricula_ra")
        tipo_pergunta = tracker.get_slot("tipo_pergunta_ra")
        parametro = tracker.get_slot("parametro_pergunta_ra")
        
        if not email:
            dispatcher.utter_message(text="Por favor, informe seu email institucional primeiro.")
            return []
        
        if not matricula_ra:
            dispatcher.utter_message(text="Nao foi possivel encontrar seu RA. Por favor, tente novamente.")
            return []
        
        # Se não tiver tipo de pergunta definido, usar padrão (digito_posicao)
        if not tipo_pergunta:
            logger.warning(f"[{self.name()}] Tipo de pergunta nao definido. Usando padrao (digito_posicao).")
            tipo_pergunta = "digito_posicao"
            parametro = "5"
        
        # Pegar a resposta do usuário
        ultima_mensagem = tracker.latest_message.get('text', '').strip()
        logger.info(f"[{self.name()}] Mensagem recebida: '{ultima_mensagem}'")
        
        # Processar resposta baseada no tipo de pergunta
        ra_resposta = None
        
        if tipo_pergunta == "completo":
            # Para RA completo, extrair todos os caracteres alfanuméricos
            caracteres = re.findall(r'[A-Za-z0-9]', ultima_mensagem.upper())
            if caracteres:
                ra_resposta = ''.join(caracteres)
            else:
                dispatcher.utter_message(text="Por favor, informe seu RA completo.")
                return []
                
        elif tipo_pergunta == "primeiros" or tipo_pergunta == "ultimos":
            # Para primeiros/últimos dígitos, extrair TODOS os caracteres alfanuméricos
            # O RA pode conter letras e números (ex: G571AF4)
            # Pode ser "G5", "G571", "g5", "G 5", etc.
            # Vamos extrair todos os caracteres alfanuméricos e remover espaços
            caracteres = re.findall(r'[A-Za-z0-9]', ultima_mensagem.upper())
            if caracteres:
                ra_resposta = ''.join(caracteres)
                # SEGURANÇA: Não logar a resposta do RA
                logger.info(f"[{self.name()}] Extraidos {len(caracteres)} caracteres da resposta do usuario")
            else:
                quantidade = int(parametro) if parametro else 4
                dispatcher.utter_message(text=f"Por favor, informe {quantidade} digitos do seu RA.")
                return []
                    
        elif tipo_pergunta == "digito_posicao":
            # Para dígito em posição, extrair apenas o primeiro caractere alfanumérico
            caracteres = re.findall(r'[A-Za-z0-9]', ultima_mensagem.upper())
            if caracteres:
                ra_resposta = caracteres[0].upper()
            else:
                dispatcher.utter_message(text="Por favor, informe o digito do RA solicitado.")
                return []
        
        if not ra_resposta:
            dispatcher.utter_message(text="Por favor, informe a resposta solicitada sobre seu RA.")
            return []
        
        # SEGURANÇA: Não logar informações sensíveis (email, RA, resposta)
        logger.info(f"[{self.name()}] Processando autenticacao. Tipo: {tipo_pergunta}, Parametro: {parametro}")
        
        try:
            # Preparar requisição para chatbot-login baseada no tipo de pergunta
            auth_request = {
                "email": email,
                "ra_resposta": ra_resposta,
                "tipo_pergunta": tipo_pergunta
            }
            
            # Adicionar parâmetros específicos conforme o tipo
            if tipo_pergunta == "primeiros":
                auth_request["quantidade_digitos"] = int(parametro) if parametro else 4
            elif tipo_pergunta == "ultimos":
                auth_request["quantidade_digitos"] = int(parametro) if parametro else 3
            elif tipo_pergunta == "digito_posicao":
                auth_request["posicao"] = int(parametro) if parametro else 5
            # Para "completo", não precisa de parâmetros adicionais
            
            
            # SEGURANÇA: Não logar a requisição completa com dados sensíveis
            logger.info(f"[{self.name()}] Enviando requisicao de autenticacao. Tipo: {tipo_pergunta}")
            
            # Fazer requisição de autenticação
            response = requests.post(
                f"{API_URL}/auth/chatbot-login",
                json=auth_request,
                timeout=10
            )
            
            response.raise_for_status()
            auth_data = response.json()
            
            # Verificar se a autenticação foi bem-sucedida
            if auth_data.get("success", False):
                access_token = auth_data.get("access_token", "")
                user_data = auth_data.get("user", {})
                
                logger.info(f"[{self.name()}] Autenticacao bem-sucedida para usuario")
                
                # SEGURANÇA: Deletar mensagens sensíveis do Telegram antes de enviar mensagem de sucesso
                # Isso remove o contexto da conversa de autenticação do histórico
                chat_id = obter_chat_id_do_tracker(tracker)
                if chat_id:
                    logger.info(f"[{self.name()}] Iniciando delecao de mensagens sensiveis do Telegram")
                    # Chamar a action de deletar mensagens (será executada na próxima iteração)
                    # Por enquanto, vamos tentar deletar diretamente aqui
                    try:
                        # Obter eventos recentes
                        events = tracker.events
                        palavras_sensiveis = ['ra', 'digito', 'primeiros', 'ultimos', 'email', 'institucional']
                        
                        for event in reversed(events[-20:]):
                            if isinstance(event, dict):
                                event_type = event.get('event')
                                text = event.get('text', '').lower()
                                
                                if any(palavra in text for palavra in palavras_sensiveis):
                                    metadata = event.get('metadata', {})
                                    message_id = metadata.get('message_id') or metadata.get('messageId')
                                    
                                    if message_id:
                                        deletar_mensagem_telegram(chat_id, message_id)
                    except Exception as e:
                        logger.warning(f"[{self.name()}] Erro ao deletar mensagens diretamente: {e}")
                
                dispatcher.utter_message(text="Autenticacao realizada com sucesso! Agora posso te ajudar com suas duvidas academicas.")
                
                # Salvar timestamp da autenticação para controle de inatividade
                timestamp_atual = datetime.now().isoformat()
                
                # Armazenar token e marcar como autenticado
                # SEGURANÇA: Limpar TODOS os slots sensíveis após autenticação bem-sucedida
                # Isso previne que informações sensíveis sejam acessadas se o dispositivo for comprometido
                return [
                    SlotSet("access_token", access_token),
                    SlotSet("autenticado", True),
                    SlotSet("ultima_atividade_timestamp", timestamp_atual),  # Salvar timestamp da autenticação
                    SlotSet("tipo_pergunta_ra", None),  # Limpar tipo de pergunta
                    SlotSet("parametro_pergunta_ra", None),  # Limpar parâmetro da pergunta
                    SlotSet("matricula_ra", None),  # Limpar RA completo (não é mais necessário)
                    SlotSet("email_institucional", None)  # Limpar email (opcional, mas aumenta segurança)
                ]
            else:
                # Autenticação falhou - RA incorreto
                mensagem_erro = auth_data.get("message", "Resposta do RA incorreta. Por favor, informe novamente.")
                dispatcher.utter_message(text=mensagem_erro)
                # SEGURANÇA: Não expor informações sensíveis nos logs
                logger.warning(f"[{self.name()}] Autenticacao falhou. Tipo de pergunta: {tipo_pergunta}")
                
                # Escolher uma nova pergunta sobre RA
                ra_length = len(matricula_ra)
                tipos_pergunta = [
                    ("primeiros", 0.3),
                    ("ultimos", 0.3),
                    ("digito_posicao", 0.35),
                    ("completo", 0.05)
                ]
                tipos, pesos = zip(*tipos_pergunta)
                tipo_escolhido = random.choices(tipos, weights=pesos, k=1)[0]
                
                parametro = None
                if tipo_escolhido == "primeiros":
                    quantidade = random.randint(2, min(4, ra_length))
                    parametro = str(quantidade)
                    pergunta = f"Quais sao os primeiros {quantidade} digitos do seu RA?"
                elif tipo_escolhido == "ultimos":
                    quantidade = random.randint(2, min(4, ra_length))
                    parametro = str(quantidade)
                    pergunta = f"Quais sao os ultimos {quantidade} digitos do seu RA?"
                elif tipo_escolhido == "digito_posicao":
                    posicao = random.randint(1, ra_length)
                    parametro = str(posicao)
                    if posicao == 1:
                        posicao_texto = "1º"
                    elif posicao == 2:
                        posicao_texto = "2º"
                    elif posicao == 3:
                        posicao_texto = "3º"
                    else:
                        posicao_texto = f"{posicao}º"
                    pergunta = f"Qual e o {posicao_texto} digito do seu RA?"
                elif tipo_escolhido == "completo":
                    pergunta = "Por favor, confirme seu RA completo."
                
                dispatcher.utter_message(text=pergunta)
                
                # Retornar slots atualizados com nova pergunta
                slots_retorno = [
                    SlotSet("matricula_ra", matricula_ra),  # Manter RA para nova tentativa
                    SlotSet("email_institucional", email),  # Manter email para nova tentativa
                    SlotSet("tipo_pergunta_ra", tipo_escolhido),
                ]
                if parametro:
                    slots_retorno.append(SlotSet("parametro_pergunta_ra", parametro))
                else:
                    slots_retorno.append(SlotSet("parametro_pergunta_ra", None))
                
                return slots_retorno
                
        except requests.exceptions.RequestException as e:
            ErrorHandler.handle_api_error(
                dispatcher, e,
                context="Autenticar via chatbot",
                action_name=self.name()
            )
            # Em caso de erro, limpar slots de pergunta e tentar novamente
            return [
                SlotSet("tipo_pergunta_ra", None),
                SlotSet("parametro_pergunta_ra", None)
            ]
        except Exception as e:
            logger.error(f"[{self.name()}] Erro inesperado: {e}")
            dispatcher.utter_message(text="Ocorreu um erro ao processar sua autenticacao. Por favor, informe a resposta sobre seu RA novamente.")
            # Limpar slots de pergunta para permitir nova tentativa
            return [
                SlotSet("tipo_pergunta_ra", None),
                SlotSet("parametro_pergunta_ra", None)
            ]


### CLASSE PARA DELETAR MENSAGENS SENSÍVEIS ###
class ActionDeletarMensagensSensiveis(Action):
    """
    Action para deletar mensagens sensíveis do Telegram após autenticação.
    Esta action procura e deleta mensagens que contenham informações sobre autenticação (RA, email, etc).
    """
    def name(self) -> Text:
        return "action_deletar_mensagens_sensiveis"
    
    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        chat_id = obter_chat_id_do_tracker(tracker)
        
        if not chat_id:
            logger.warning(f"[{self.name()}] Chat ID nao encontrado. Nao e possivel deletar mensagens.")
            return []
        
        logger.info(f"[{self.name()}] Tentando deletar mensagens sensiveis do chat {chat_id}")
        
        # Palavras-chave que indicam mensagens sensíveis
        palavras_sensiveis = ['ra', 'digito', 'primeiros', 'ultimos', 'email', 'institucional', 'autenticacao', 'autenticação']
        
        mensagens_deletadas = 0
        mensagens_nao_encontradas = 0
        
        # Obter eventos recentes do tracker
        try:
            events = tracker.events
            
            # Procurar por mensagens do bot que contenham informações sensíveis
            # Verificar últimos 30 eventos (cobre várias mensagens)
            for event in reversed(events[-30:]):
                if isinstance(event, dict):
                    event_type = event.get('event')
                    
                    # Verificar mensagens do bot
                    if event_type == 'bot':
                        text = event.get('text', '')
                        text_lower = text.lower()
                        
                        # Verificar se contém palavras sensíveis
                        if any(palavra in text_lower for palavra in palavras_sensiveis):
                            # Tentar obter message_id do metadata
                            metadata = event.get('metadata', {})
                            message_id = metadata.get('message_id') or metadata.get('messageId')
                            
                            if message_id:
                                if deletar_mensagem_telegram(chat_id, message_id):
                                    mensagens_deletadas += 1
                                else:
                                    mensagens_nao_encontradas += 1
                            else:
                                logger.debug(f"[{self.name()}] Message ID nao encontrado para mensagem: {text[:50]}...")
                    
                    # Verificar também mensagens do usuário que possam conter informações sensíveis
                    elif event_type == 'user':
                        text = event.get('text', '')
                        text_lower = text.lower()
                        
                        # Verificar se contém informações sensíveis (email, resposta do RA)
                        if any(palavra in text_lower for palavra in palavras_sensiveis) or '@' in text_lower:
                            metadata = event.get('metadata', {})
                            message_id = metadata.get('message_id') or metadata.get('messageId')
                            
                            if message_id:
                                if deletar_mensagem_telegram(chat_id, message_id):
                                    mensagens_deletadas += 1
                                else:
                                    mensagens_nao_encontradas += 1
        
        except Exception as e:
            logger.error(f"[{self.name()}] Erro ao processar eventos para deletar mensagens: {e}")
        
        if mensagens_deletadas > 0:
            logger.info(f"[{self.name()}] {mensagens_deletadas} mensagem(ns) sensivel(is) deletada(s) com sucesso")
        elif mensagens_nao_encontradas > 0:
            logger.warning(f"[{self.name()}] Tentou deletar {mensagens_nao_encontradas} mensagem(ns) mas nao foi possivel (pode ter passado 48h)")
        else:
            logger.info(f"[{self.name()}] Nenhuma mensagem sensivel encontrada para deletar")
        
        return []


### CLASSE PARA ESCOLHER PERGUNTA SOBRE RA ###
class ActionEscolherPerguntaRA(Action):
    """
    Action para escolher aleatoriamente o tipo de pergunta sobre o RA.
    Tipos disponíveis:
    - primeiros: primeiros N dígitos
    - ultimos: últimos N dígitos
    - digito_posicao: dígito em posição específica
    - completo: RA completo (para validação final)
    """
    def name(self) -> Text:
        return "action_escolher_pergunta_ra"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        matricula_ra = tracker.get_slot("matricula_ra")
        
        if not matricula_ra:
            logger.error(f"[{self.name()}] RA nao encontrado. Nao e possivel escolher pergunta.")
            return []
        
        ra_length = len(matricula_ra)
        
        # Tipos de pergunta disponíveis (pesos para distribuição)
        # Vamos dar mais peso para perguntas parciais e menos para completo
        tipos_pergunta = [
            ("primeiros", 0.3),
            ("ultimos", 0.3),
            ("digito_posicao", 0.35),
            ("completo", 0.05)  # Menos frequente para maior segurança
        ]
        
        # Escolher tipo aleatoriamente baseado nos pesos
        tipos, pesos = zip(*tipos_pergunta)
        tipo_escolhido = random.choices(tipos, weights=pesos, k=1)[0]
        
        # SEGURANÇA: Não logar informações sobre o RA
        logger.info(f"[{self.name()}] Tipo de pergunta escolhido: {tipo_escolhido}")
        
        parametro = None
        
        if tipo_escolhido == "primeiros":
            # Escolher quantidade entre 2 e min(4, ra_length)
            quantidade = random.randint(2, min(4, ra_length))
            parametro = str(quantidade)
            
        elif tipo_escolhido == "ultimos":
            # Escolher quantidade entre 2 e min(4, ra_length)
            quantidade = random.randint(2, min(4, ra_length))
            parametro = str(quantidade)
            
        elif tipo_escolhido == "digito_posicao":
            # Escolher posição aleatória (1-indexed)
            posicao = random.randint(1, ra_length)
            parametro = str(posicao)
            
        elif tipo_escolhido == "completo":
            # Não precisa de parâmetro
            parametro = None
        
        # SEGURANÇA: Log apenas do tipo e parâmetro, não do RA
        logger.info(f"[{self.name()}] Tipo: {tipo_escolhido}, Parametro: {parametro}")
        
        slots = [SlotSet("tipo_pergunta_ra", tipo_escolhido)]
        if parametro:
            slots.append(SlotSet("parametro_pergunta_ra", parametro))
        else:
            slots.append(SlotSet("parametro_pergunta_ra", None))
        
        return slots


### CLASSE PARA FAZER PERGUNTA SOBRE RA ###
class ActionFazerPerguntaRA(Action):
    """
    Action para fazer a pergunta sobre o RA baseada no tipo escolhido.
    """
    def name(self) -> Text:
        return "action_fazer_pergunta_ra"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        tipo_pergunta = tracker.get_slot("tipo_pergunta_ra")
        parametro = tracker.get_slot("parametro_pergunta_ra")
        
        if not tipo_pergunta:
            logger.warning(f"[{self.name()}] Tipo de pergunta nao definido. Usando padrao (digito_posicao).")
            tipo_pergunta = "digito_posicao"
            parametro = "5"
            # Definir slots
            return [
                SlotSet("tipo_pergunta_ra", tipo_pergunta),
                SlotSet("parametro_pergunta_ra", parametro)
            ]
        
        # Gerar pergunta baseada no tipo
        pergunta = ""
        
        if tipo_pergunta == "primeiros":
            quantidade = int(parametro) if parametro else 4
            pergunta = f"Quais sao os primeiros {quantidade} digitos do seu RA?"
            
        elif tipo_pergunta == "ultimos":
            quantidade = int(parametro) if parametro else 3
            pergunta = f"Quais sao os ultimos {quantidade} digitos do seu RA?"
            
        elif tipo_pergunta == "digito_posicao":
            posicao = int(parametro) if parametro else 5
            # Formatar posição (1º, 2º, 3º, etc.)
            if posicao == 1:
                posicao_texto = "1º"
            elif posicao == 2:
                posicao_texto = "2º"
            elif posicao == 3:
                posicao_texto = "3º"
            else:
                posicao_texto = f"{posicao}º"
            pergunta = f"Qual e o {posicao_texto} digito do seu RA?"
            
        elif tipo_pergunta == "completo":
            pergunta = "Por favor, confirme seu RA completo."
        else:
            # Fallback
            pergunta = "Agora informe o 5º digito do seu RA?"
        
        # SEGURANÇA: Não logar a pergunta completa (pode conter informações sobre o RA)
        logger.info(f"[{self.name()}] Fazendo pergunta de autenticacao. Tipo: {tipo_pergunta}")
        dispatcher.utter_message(text=pergunta)
        
        return []


### CLASSE PARA CONSULTAR QUANTIDADE DE ALUNOS NA TURMA ###
class ActionConsultarQuantidadeAlunosTurma(Action):
    """
    Action para consultar quantos alunos tem na mesma turma do aluno autenticado.
    """
    def name(self) -> Text:
        return "action_consultar_quantidade_alunos_turma"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        # PRIMEIRO: Verificar inatividade (pode deslogar se inativo)
        ainda_autenticado, eventos_inatividade = verificar_e_atualizar_inatividade(tracker, dispatcher)
        if not ainda_autenticado:
            return eventos_inatividade
        
        # SEGUNDO: Verificar autenticação completa
        autenticado, access_token = verificar_autenticacao_completa(tracker)
        
        if not autenticado or not access_token:
            dispatcher.utter_message(text="Voce precisa estar autenticado para consultar informacoes da sua turma. Por favor, faca login primeiro.")
            logger.warning(f"[{self.name()}] Tentativa de consultar turma sem autenticacao valida")
            return eventos_inatividade
        
        # Enviar indicador de digitando
        chat_id = obter_chat_id_do_tracker(tracker)
        if chat_id:
            enviar_indicador_digitando(chat_id)
        
        try:
            # Decodificar o token JWT para obter o user_id
            # O secret é a SUPABASE_SERVICE_KEY, mas como não temos acesso direto aqui,
            # vamos usar uma abordagem alternativa: fazer uma requisição autenticada
            # que retorna o user_id, ou decodificar sem verificar (menos seguro, mas funcional)
            # Por enquanto, vamos tentar decodificar sem verificar para obter o user_id
            try:
                # Decodificar sem verificar (apenas para obter o payload)
                # Em produção, seria melhor ter um endpoint que retorna o user_id do token
                decoded_token = jwt.decode(access_token, options={"verify_signature": False})
                user_id = decoded_token.get("user_id")
                
                if not user_id:
                    logger.error(f"[{self.name()}] user_id nao encontrado no token")
                    dispatcher.utter_message(text="Erro ao identificar seu usuario. Por favor, faca login novamente.")
                    return []
            except Exception as jwt_error:
                logger.error(f"[{self.name()}] Erro ao decodificar token: {jwt_error}")
                dispatcher.utter_message(text="Erro ao processar sua autenticacao. Por favor, faca login novamente.")
                return []
            
            # Chamar o endpoint para obter informações da turma
            headers = get_auth_headers(tracker, verificar_validade=True)
            if "Authorization" not in headers:
                dispatcher.utter_message(text="Sessao expirada. Por favor, faca a autenticacao novamente enviando uma saudacao.")
                logger.error(f"[{self.name()}] Token de autenticacao nao disponivel ou invalido")
                return []
            
            response = requests.get(
                f"{API_URL}/alunos/get_quantidade_turma/{user_id}",
                headers=headers,
                timeout=10
            )
            
            if response.status_code == 404:
                dispatcher.utter_message(text="Nao foi possivel encontrar suas informacoes de turma. Por favor, entre em contato com a secretaria.")
                logger.warning(f"[{self.name()}] Aluno nao encontrado: {user_id}")
                return []
            
            response.raise_for_status()
            data = response.json()
            
            quantidade_alunos = data.get("quantidade_alunos", 0)
            nome_curso = data.get("nome_curso", "")
            turma = data.get("turma", "")
            semestre = data.get("semestre", 0)
            
            # Formatar código da turma: CC8P33
            # CC = iniciais das palavras principais do nome do curso (abreviação)
            # 8 = semestre
            # P = turma
            # 33 = valor fixo
            
            # Função para obter as iniciais das palavras principais (ignorando artigos e preposições)
            def obter_abreviacao_curso(nome: str) -> str:
                # Palavras a ignorar (artigos e preposições) - todas em minúsculas para comparação
                palavras_ignorar = {'da', 'de', 'do', 'das', 'dos', 'e', 'em', 'na', 'no', 'nas', 'nos', 'a', 'o', 'as', 'os'}
                
                # Normalizar: remover espaços extras e dividir em palavras
                palavras = nome.strip().split()
                iniciais = []
                
                for palavra in palavras:
                    # Remover espaços e converter para minúsculas para comparação
                    palavra_limpa = palavra.strip().lower()
                    
                    # Ignorar palavras vazias ou na lista de ignorar
                    if palavra_limpa and palavra_limpa not in palavras_ignorar:
                        # Pegar a primeira letra em maiúscula
                        primeira_letra = palavra_limpa[0].upper()
                        iniciais.append(primeira_letra)
                
                # Se não encontrou iniciais, usar as duas primeiras letras do nome (ignorando espaços)
                if not iniciais:
                    nome_sem_espacos = ''.join(nome.split())
                    return nome_sem_espacos[:2].upper() if len(nome_sem_espacos) >= 2 else nome.upper()
                
                # Retornar as duas primeiras iniciais (ou apenas uma se houver só uma)
                if len(iniciais) >= 2:
                    return ''.join(iniciais[:2])
                elif len(iniciais) == 1:
                    # Se só tem uma inicial, repetir para ter duas letras
                    return iniciais[0] * 2
                else:
                    # Fallback: usar as duas primeiras letras do nome
                    nome_sem_espacos = ''.join(nome.split())
                    return nome_sem_espacos[:2].upper() if len(nome_sem_espacos) >= 2 else nome.upper()
            
            abreviacao_curso = obter_abreviacao_curso(nome_curso)
            
            # Formatar código da turma
            codigo_turma = f"{abreviacao_curso}{semestre}{turma.upper()}33"
            
            # Formatar resposta
            mensagem = f"Na sua turma {codigo_turma} tem {quantidade_alunos} alunos."
            
            dispatcher.utter_message(text=mensagem)
            logger.info(f"[{self.name()}] Consulta de turma realizada com sucesso para aluno {user_id}")
            
            return []
            
        except requests.exceptions.RequestException as e:
            ErrorHandler.handle_api_error(
                dispatcher, e,
                context="Consultar quantidade de alunos na turma",
                action_name=self.name()
            )
            return []
        except Exception as e:
            logger.error(f"[{self.name()}] Erro inesperado: {e}")
            dispatcher.utter_message(text="Ocorreu um erro ao consultar as informacoes da sua turma. Tente novamente.")
            return []

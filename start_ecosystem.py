#!/usr/bin/env python3
"""
Script para iniciar automaticamente todo o ecossistema do ChatBot Acadêmico
Inclui: API FastAPI, Servidores Rasa, e preparado para Flask (painel web)

Uso: 
    python3 start_ecosystem.py
    python3 start_ecosystem.py --ngrok-url https://seu-ngrok-id.ngrok-free.app
"""

import os
import sys
import subprocess
import signal
import time
import threading
import socket
import argparse
import re
from pathlib import Path
from queue import Queue

# Tentar importar dotenv, se não estiver disponível, usar fallback
try:
    from dotenv import load_dotenv, set_key, dotenv_values
    DOTENV_AVAILABLE = True
except ImportError:
    DOTENV_AVAILABLE = False
    print("⚠️  python-dotenv não está instalado. Instale com: pip install python-dotenv")
    print("   Funcionalidades de .env serão limitadas.")

# Cores para output
GREEN = '\033[0;32m'
YELLOW = '\033[1;33m'
RED = '\033[0;31m'
BLUE = '\033[0;34m'
CYAN = '\033[0;36m'
NC = '\033[0m'  # No Color

# Processos
processes = []

# Threads para logs
log_threads = []


def log_reader(process, prefix, color):
    """Lê logs de um processo e exibe com prefixo colorido"""
    try:
        for line in iter(process.stdout.readline, ''):
            if line:
                print(f"{color}[{prefix}]{NC} {line.rstrip()}")
        process.stdout.close()
    except Exception as e:
        print(f"{RED}Erro ao ler logs de {prefix}: {e}{NC}")


def cleanup(signum=None, frame=None):
    """Para todos os processos ao receber sinal"""
    print(f"\n{YELLOW}Parando todos os serviços...{NC}")
    
    # Parar processos
    for process in processes:
        try:
            process.terminate()
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
        except Exception as e:
            print(f"{RED}Erro ao parar processo: {e}{NC}")
    
    # Aguardar threads de log terminarem
    for thread in log_threads:
        thread.join(timeout=2)
    
    # Limpar arquivo temporário de credentials processado
    processed_credentials = Path("chatbot_rasa/credentials.yml.processed")
    if processed_credentials.exists():
        try:
            processed_credentials.unlink()
        except Exception as e:
            print(f"{YELLOW}⚠ Não foi possível remover arquivo temporário: {e}{NC}")
    
    print(f"{GREEN}Todos os serviços parados.{NC}")
    sys.exit(0)


# Registrar handlers de sinal
signal.signal(signal.SIGINT, cleanup)
signal.signal(signal.SIGTERM, cleanup)


def get_windows_host_ip():
    """
    Obtém o IP do Windows host na rede local (não o IP do WSL/Hyper-V).
    Prioriza IPs na faixa de rede local (192.168.x.x, 10.x.x.x).
    Ignora IPs do WSL/Hyper-V (172.28.x.x, 172.27.x.x, etc).
    """
    # Lista de IPs para tentar obter
    ip_candidates = []
    
    # Método 1: Tentar obter IPs via PowerShell do Windows (mais confiável)
    try:
        # Comando PowerShell para pegar IPs IPv4, excluindo adaptadores WSL/Hyper-V
        ps_command = (
            "Get-NetIPAddress -AddressFamily IPv4 | "
            "Where-Object {"
            "$_.IPAddress -notlike '172.28.*' -and "
            "$_.IPAddress -notlike '172.27.*' -and "
            "$_.IPAddress -notlike '169.254.*' -and "
            "$_.InterfaceAlias -notlike '*WSL*' -and "
            "$_.InterfaceAlias -notlike '*Hyper-V*'"
            "} | "
            "Select-Object -ExpandProperty IPAddress"
        )
        
        result = subprocess.run(
            ["powershell.exe", "-Command", ps_command],
            capture_output=True,
            text=True,
            timeout=5
        )
        
        if result.returncode == 0 and result.stdout.strip():
            for ip in result.stdout.strip().split('\n'):
                ip = ip.strip()
                if ip and ip != '':
                    # Filtrar IPs do WSL
                    if not ip.startswith('172.28') and not ip.startswith('172.27'):
                        ip_candidates.append(ip)
    except Exception as e:
        # Se PowerShell falhar, tenta método alternativo
        pass
    
    # Método 2: Tentar via ipconfig do Windows (fallback)
    if not ip_candidates:
        try:
            result = subprocess.run(
                ["cmd.exe", "/c", "ipconfig | findstr IPv4"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0 and result.stdout.strip():
                for line in result.stdout.strip().split('\n'):
                    if 'IPv4' in line:
                        # Extrair IP da linha (formato: "Endereço IPv4. . . . . . . . . . . . . . . . . . : 192.168.1.99")
                        parts = line.split(':')
                        if len(parts) > 1:
                            ip = parts[-1].strip()
                            if ip and not ip.startswith('172.28') and not ip.startswith('172.27'):
                                ip_candidates.append(ip)
        except:
            pass
    
    # Priorizar IPs de rede local (192.168.x.x ou 10.x.x.x)
    for ip in ip_candidates:
        if ip.startswith('192.168.') or ip.startswith('10.'):
            return ip
    
    # Se não encontrou IP de rede local, retornar o primeiro que não seja do WSL
    for ip in ip_candidates:
        if ip and not ip.startswith('172.28') and not ip.startswith('172.27'):
            return ip
    
    # Se ainda não encontrou, retornar None (será tratado na exibição)
    return None


def check_directory():
    """Verifica se estamos no diretório raiz correto"""
    root_path = Path(__file__).parent.absolute()
    chatbot_rasa = root_path / "chatbot_rasa"
    chatbot_api = root_path / "chatbot_api"
    chatbot_web = root_path / "chatbot_web"  # Nome correto do diretório
    
    if not chatbot_rasa.exists() or not chatbot_api.exists():
        print(f"{RED}Erro: Execute este script no diretório raiz do projeto{NC}")
        print(f"Diretório atual: {root_path}")
        print("Exemplo: cd ~/TCC-ChatBotAcademico && python3 start_ecosystem.py")
        sys.exit(1)
    
    return root_path, chatbot_rasa, chatbot_api, chatbot_web


def check_venv_api(api_path):
    """Verifica e prepara o ambiente virtual da API"""
    venv_path = api_path / ".venv_api"
    
    if not venv_path.exists():
        print(f"{YELLOW}Ambiente virtual da API não encontrado. Criando...{NC}")
        subprocess.run([sys.executable, "-m", "venv", ".venv_api"], 
                      cwd=api_path, check=True)
        print(f"{GREEN}✓ Ambiente virtual da API criado{NC}")
    
    # Determinar o Python do venv
    if sys.platform == "win32":
        python_venv = venv_path / "Scripts" / "python.exe"
    else:
        python_venv = venv_path / "bin" / "python"
    
    if not python_venv.exists():
        print(f"{RED}Erro: Python do ambiente virtual da API não encontrado{NC}")
        sys.exit(1)
    
    return str(python_venv)


def check_venv_rasa(rasa_path):
    """Verifica e prepara o ambiente virtual do Rasa"""
    venv_path = rasa_path / ".venv_rasa"
    
    if not venv_path.exists():
        print(f"{YELLOW}Ambiente virtual do Rasa não encontrado. Criando...{NC}")
        subprocess.run([sys.executable, "-m", "venv", ".venv_rasa"], 
                      cwd=rasa_path, check=True)
        print(f"{GREEN}✓ Ambiente virtual do Rasa criado{NC}")
    
    # Determinar o Python do venv
    if sys.platform == "win32":
        python_venv = venv_path / "Scripts" / "python.exe"
    else:
        python_venv = venv_path / "bin" / "python"
    
    if not python_venv.exists():
        print(f"{RED}Erro: Python do ambiente virtual do Rasa não encontrado{NC}")
        sys.exit(1)
    
    return str(python_venv)


def check_venv_flask(flask_path):
    """Verifica e prepara o ambiente virtual do Flask (opcional)"""
    if not flask_path.exists():
        return None
    
    venv_path = flask_path / "venv_web"
    
    if not venv_path.exists():
        print(f"{YELLOW}Ambiente virtual do Flask não encontrado. Criando...{NC}")
        try:
            subprocess.run([sys.executable, "-m", "venv", "venv_web"], 
                          cwd=flask_path, check=True)
            print(f"{GREEN}✓ Ambiente virtual do Flask criado{NC}")
        except Exception as e:
            print(f"{YELLOW}⚠ Erro ao criar ambiente virtual do Flask: {e}{NC}")
            return None
    
    # Determinar o Python do venv
    if sys.platform == "win32":
        python_venv = venv_path / "Scripts" / "python.exe"
    else:
        python_venv = venv_path / "bin" / "python"
    
    if not python_venv.exists():
        print(f"{YELLOW}⚠ Python do ambiente virtual do Flask não encontrado{NC}")
        return None
    
    return str(python_venv)


def load_rasa_env(rasa_path, ngrok_url=None):
    """Carrega variáveis de ambiente do .env do Rasa e atualiza se necessário"""
    if not DOTENV_AVAILABLE:
        print(f"{RED}Erro: python-dotenv não está instalado{NC}")
        print(f"{YELLOW}Instale com: pip install python-dotenv{NC}")
        return False
    
    env_path = rasa_path / ".env"
    
    # Se ngrok_url foi fornecido, atualizar o .env
    if ngrok_url:
        # Garantir que a URL termine com /webhooks/telegram/webhook
        if not ngrok_url.endswith("/webhooks/telegram/webhook"):
            if ngrok_url.endswith("/"):
                ngrok_url = ngrok_url + "webhooks/telegram/webhook"
            else:
                ngrok_url = ngrok_url + "/webhooks/telegram/webhook"
        
        # Criar ou atualizar o arquivo .env
        if env_path.exists():
            # Atualizar variável existente
            try:
                set_key(str(env_path), "TELEGRAM_WEBHOOK_URL", ngrok_url)
                print(f"{GREEN}✓ URL do ngrok atualizada no .env: {ngrok_url}{NC}")
            except Exception as e:
                print(f"{YELLOW}⚠ Erro ao atualizar .env: {e}{NC}")
                # Tentar atualizar manualmente
                try:
                    with open(env_path, "r", encoding="utf-8") as f:
                        content = f.read()
                    # Substituir ou adicionar a linha
                    lines = content.split("\n")
                    updated = False
                    for i, line in enumerate(lines):
                        if line.startswith("TELEGRAM_WEBHOOK_URL="):
                            lines[i] = f"TELEGRAM_WEBHOOK_URL={ngrok_url}"
                            updated = True
                            break
                    if not updated:
                        lines.append(f"TELEGRAM_WEBHOOK_URL={ngrok_url}")
                    with open(env_path, "w", encoding="utf-8") as f:
                        f.write("\n".join(lines))
                    print(f"{GREEN}✓ URL do ngrok atualizada manualmente no .env{NC}")
                except Exception as e2:
                    print(f"{RED}Erro ao atualizar .env manualmente: {e2}{NC}")
        else:
            # Criar arquivo .env com valores padrão (se necessário)
            print(f"{YELLOW}⚠ Arquivo .env não encontrado. Criando...{NC}")
            # Será criado pelo setup_env.py se necessário
    
    # Carregar variáveis de ambiente
    if env_path.exists():
        try:
            load_dotenv(env_path)
            print(f"{GREEN}✓ Variáveis de ambiente do Rasa carregadas{NC}")
        except Exception as e:
            print(f"{YELLOW}⚠ Erro ao carregar .env: {e}{NC}")
    else:
        print(f"{YELLOW}⚠ Arquivo .env do Rasa não encontrado{NC}")
        print(f"{YELLOW}  Execute: cd chatbot_rasa && python3 setup_env.py{NC}")
    
    # Validar variáveis obrigatórias
    required_vars = ["TELEGRAM_ACCESS_TOKEN", "TELEGRAM_VERIFY", "TELEGRAM_WEBHOOK_URL"]
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    if missing_vars:
        print(f"{RED}Erro: Variáveis de ambiente obrigatórias não encontradas:{NC}")
        for var in missing_vars:
            print(f"{RED}  - {var}{NC}")
        print(f"\n{YELLOW}Configure o arquivo chatbot_rasa/.env com as variáveis necessárias.{NC}")
        return False
    
    return True


def process_credentials_file(rasa_path):
    """Processa o arquivo credentials.yml substituindo variáveis de ambiente"""
    credentials_path = rasa_path / "credentials.yml"
    credentials_processed_path = rasa_path / "credentials.yml.processed"
    
    if not credentials_path.exists():
        return None
    
    # Ler o arquivo original
    with open(credentials_path, "r", encoding="utf-8") as f:
        content = f.read()
    
    # Substituir variáveis de ambiente no formato ${VAR}
    def replace_env_var(match):
        var_name = match.group(1)
        value = os.getenv(var_name)
        if value is None:
            print(f"{YELLOW}⚠ Aviso: Variável {var_name} não encontrada, mantendo placeholder{NC}")
            return match.group(0)  # Mantém o placeholder original
        return value
    
    # Substituir ${VAR} pelas variáveis de ambiente
    processed_content = re.sub(r'\$\{([^}]+)\}', replace_env_var, content)
    
    # Escrever o arquivo processado
    with open(credentials_processed_path, "w", encoding="utf-8") as f:
        f.write(processed_content)
    
    return str(credentials_processed_path)


def start_api(api_path, python_venv):
    """Inicia o servidor da API FastAPI"""
    print(f"\n{BLUE}[1/3] Iniciando API FastAPI (porta 8000)...{NC}")
    
    api_process = subprocess.Popen(
        [python_venv, "-m", "uvicorn", "src.main:app", 
         "--host", "0.0.0.0", "--port", "8000", "--reload"],
        cwd=api_path,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        universal_newlines=True
    )
    
    processes.append(api_process)
    
    # Criar thread para ler logs
    log_thread = threading.Thread(
        target=log_reader,
        args=(api_process, "API", BLUE),
        daemon=True
    )
    log_thread.start()
    log_threads.append(log_thread)
    
    # Aguardar um pouco para o servidor iniciar
    time.sleep(3)
    
    # Verificar se o processo ainda está rodando
    if api_process.poll() is not None:
        print(f"{RED}Erro ao iniciar API FastAPI{NC}")
        return False
    
    print(f"{GREEN}✓ API FastAPI iniciada (PID: {api_process.pid}){NC}")
    return True


def start_rasa(rasa_path, python_venv, env=None):
    """Inicia os servidores do Rasa usando o script start_rasa.py"""
    print(f"\n{CYAN}[2/3] Iniciando servidores do Rasa...{NC}")
    
    # Verificar se o script start_rasa.py existe
    start_rasa_script = rasa_path / "start_rasa.py"
    if not start_rasa_script.exists():
        print(f"{RED}Erro: start_rasa.py não encontrado em {rasa_path}{NC}")
        return False
    
    # Processar credentials.yml antes de iniciar
    processed_credentials = process_credentials_file(rasa_path)
    if processed_credentials:
        print(f"{GREEN}✓ Arquivo credentials.yml processado{NC}")
    
    # Preparar ambiente para subprocesso (incluindo variáveis do .env)
    if env is None:
        env = os.environ.copy()
    
    # Iniciar o script do Rasa
    rasa_process = subprocess.Popen(
        [python_venv, "start_rasa.py"],
        cwd=rasa_path,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        universal_newlines=True,
        env=env
    )
    
    processes.append(rasa_process)
    
    # Criar thread para ler logs
    log_thread = threading.Thread(
        target=log_reader,
        args=(rasa_process, "RASA", CYAN),
        daemon=True
    )
    log_thread.start()
    log_threads.append(log_thread)
    
    # Aguardar um pouco para os servidores iniciarem
    time.sleep(5)
    
    # Verificar se o processo ainda está rodando
    if rasa_process.poll() is not None:
        print(f"{RED}Erro ao iniciar servidores do Rasa{NC}")
        return False
    
    print(f"{GREEN}✓ Servidores do Rasa iniciados (PID: {rasa_process.pid}){NC}")
    print(f"{GREEN}  - Servidor de Actions: porta 5055{NC}")
    print(f"{GREEN}  - Servidor Principal: porta 5005{NC}")
    return True


def start_flask_panel(flask_path, python_venv):
    """Inicia o servidor Flask do painel web"""
    print(f"\n{YELLOW}[3/4] Iniciando servidor Flask (painel web)...{NC}")
    
    if not flask_path.exists():
        print(f"{YELLOW}Diretório do Flask não encontrado. Pulando...{NC}")
        return True
    
    # Verificar se app.py existe
    app_file = flask_path / "app.py"
    if not app_file.exists():
        print(f"{YELLOW}app.py não encontrado em {flask_path}. Pulando...{NC}")
        return True
    
    flask_process = subprocess.Popen(
        [python_venv, "app.py"],
        cwd=flask_path,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        universal_newlines=True
    )
    
    processes.append(flask_process)
    
    # Criar thread para ler logs
    log_thread = threading.Thread(
        target=log_reader,
        args=(flask_process, "FLASK", YELLOW),
        daemon=True
    )
    log_thread.start()
    log_threads.append(log_thread)
    
    # Aguardar um pouco para o servidor iniciar
    time.sleep(3)
    
    # Verificar se o processo ainda está rodando
    if flask_process.poll() is not None:
        print(f"{RED}Erro ao iniciar servidor Flask{NC}")
        return False
    
    print(f"{GREEN}✓ Servidor Flask iniciado (PID: {flask_process.pid}){NC}")
    return True


def parse_arguments():
    """Parse argumentos da linha de comando"""
    parser = argparse.ArgumentParser(
        description="Inicia o ecossistema completo do ChatBot Acadêmico",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemplos de uso:
  python3 start_ecosystem.py
  python3 start_ecosystem.py --ngrok-url https://abc123.ngrok-free.app
  python3 start_ecosystem.py --ngrok-url https://abc123.ngrok-free.app/webhooks/telegram/webhook
        """
    )
    parser.add_argument(
        "--ngrok-url",
        type=str,
        help="URL do ngrok para o webhook do Telegram (será adicionado /webhooks/telegram/webhook se necessário)"
    )
    return parser.parse_args()


def main():
    """Função principal"""
    # Parse argumentos
    args = parse_arguments()
    
    print(f"{GREEN}{'='*60}{NC}")
    print(f"{GREEN}  Iniciando Ecossistema do ChatBot Acadêmico{NC}")
    print(f"{GREEN}{'='*60}{NC}")
    
    # Verificar diretórios
    root_path, chatbot_rasa, chatbot_api, chatbot_web = check_directory()
    
    print(f"\n{CYAN}Diretórios encontrados:{NC}")
    print(f"  - Raiz: {root_path}")
    print(f"  - Rasa: {chatbot_rasa}")
    print(f"  - API: {chatbot_api}")
    print(f"  - Flask: {chatbot_web} {'✓' if chatbot_web.exists() else '(não encontrado - opcional)'}")
    
    # Carregar e validar variáveis de ambiente do Rasa
    print(f"\n{YELLOW}Carregando configurações do Rasa...{NC}")
    if not load_rasa_env(chatbot_rasa, args.ngrok_url):
        print(f"{RED}Erro ao carregar configurações do Rasa. Abortando...{NC}")
        sys.exit(1)
    
    # Preparar ambientes virtuais
    print(f"\n{YELLOW}Verificando ambientes virtuais...{NC}")
    python_venv_api = check_venv_api(chatbot_api)
    python_venv_rasa = check_venv_rasa(chatbot_rasa)
    python_venv_flask = check_venv_flask(chatbot_web)
    
    # Preparar ambiente para subprocessos (incluindo variáveis do .env do Rasa)
    env = os.environ.copy()
    
    # Iniciar serviços
    try:
        # 1. API FastAPI
        if not start_api(chatbot_api, python_venv_api):
            print(f"{RED}Falha ao iniciar API. Abortando...{NC}")
            cleanup()
            sys.exit(1)
        
        # 2. Servidores Rasa
        if not start_rasa(chatbot_rasa, python_venv_rasa, env):
            print(f"{RED}Falha ao iniciar servidores Rasa. Abortando...{NC}")
            cleanup()
            sys.exit(1)
        
        # 3. Servidor Flask (opcional)
        if python_venv_flask:
            if not start_flask_panel(chatbot_web, python_venv_flask):
                print(f"{YELLOW}Aviso: Falha ao iniciar servidor Flask, mas continuando...{NC}")
        else:
            print(f"{YELLOW}⚠ Servidor Flask não disponível (diretório não encontrado ou venv não configurado){NC}")
        
        # Obter IP do Windows host
        windows_ip = get_windows_host_ip()
        
        # Resumo
        print(f"\n{GREEN}{'='*60}{NC}")
        print(f"{GREEN}  Todos os serviços iniciados com sucesso!{NC}")
        print(f"{GREEN}{'='*60}{NC}")
        print(f"\n{CYAN}Serviços rodando:{NC}")
        print(f"  {GREEN}✓{NC} API FastAPI: http://localhost:8000")
        if windows_ip:
            print(f"              {CYAN}(ou http://{windows_ip}:8000 para acesso externo){NC}")
        print(f"  {GREEN}✓{NC} Rasa Actions: http://localhost:5055")
        print(f"  {GREEN}✓{NC} Rasa Server: http://localhost:5005")
        if windows_ip:
            print(f"              {CYAN}(ou http://{windows_ip}:5005 para acesso externo){NC}")
        else:
            print(f"              {YELLOW}(IP do Windows host não detectado automaticamente){NC}")
            print(f"              {YELLOW}Para descobrir: ip route show default | awk '/default/ {{print $3}}'{NC}")
        if python_venv_flask:
            print(f"  {GREEN}✓{NC} Flask Panel: http://localhost:5001")
            if windows_ip:
                print(f"              {CYAN}(ou http://{windows_ip}:5001 para acesso externo){NC}")
        else:
            print(f"  {YELLOW}⚠{NC} Flask Panel: não disponível")
        print(f"\n{CYAN}Logs em tempo real:{NC}")
        print(f"  {BLUE}[API]{NC} - Logs da API FastAPI")
        print(f"  {CYAN}[RASA]{NC} - Logs dos servidores Rasa")
        print(f"  {YELLOW}[FLASK]{NC} - Logs do servidor Flask")
        print(f"\n{YELLOW}Pressione Ctrl+C para parar todos os serviços{NC}")
        print(f"{GREEN}{'='*60}{NC}\n")
        
        # Aguardar indefinidamente (ou até Ctrl+C)
        try:
            while True:
                # Verificar se algum processo morreu
                for i, process in enumerate(processes):
                    if process.poll() is not None:
                        print(f"{RED}Processo {i} terminou inesperadamente{NC}")
                        cleanup()
                        sys.exit(1)
                time.sleep(1)
        except KeyboardInterrupt:
            pass
            
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print(f"{RED}Erro: {e}{NC}")
        import traceback
        traceback.print_exc()
    finally:
        cleanup()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        cleanup()
    except Exception as e:
        print(f"{RED}Erro fatal: {e}{NC}")
        cleanup()
        sys.exit(1)


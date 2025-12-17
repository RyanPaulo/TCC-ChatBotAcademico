#!/usr/bin/env python3
"""
Script para iniciar automaticamente os servidores do Rasa
Uso: python3 start_rasa.py
"""

import os
import sys
import subprocess
import signal
import time
import threading
import re
import shutil
from pathlib import Path
from dotenv import load_dotenv

# Cores para output
GREEN = '\033[0;32m'
YELLOW = '\033[1;33m'
RED = '\033[0;31m'
CYAN = '\033[0;36m'
NC = '\033[0m'  # No Color

# Processos
processes = []


def cleanup(signum=None, frame=None):
    """Para todos os processos ao receber sinal"""
    print(f"\n{YELLOW}Parando servidores...{NC}")
    for process in processes:
        try:
            process.terminate()
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
        except Exception as e:
            print(f"{RED}Erro ao parar processo: {e}{NC}")
    
    # Limpar arquivo temporário de credentials processado
    processed_credentials = Path("credentials.yml.processed")
    if processed_credentials.exists():
        try:
            processed_credentials.unlink()
        except Exception as e:
            print(f"{YELLOW}⚠ Não foi possível remover arquivo temporário: {e}{NC}")
    
    print(f"{GREEN}Servidores parados.{NC}")
    sys.exit(0)


# Registrar handlers de sinal
signal.signal(signal.SIGINT, cleanup)
signal.signal(signal.SIGTERM, cleanup)


def check_venv():
    """Verifica e ativa o ambiente virtual"""
    venv_path = Path(".venv_rasa")
    
    if not venv_path.exists():
        print(f"{YELLOW}Ambiente virtual não encontrado. Criando...{NC}")
        subprocess.run([sys.executable, "-m", "venv", ".venv_rasa"], check=True)
        print(f"{GREEN}✓ Ambiente virtual criado{NC}")
    
    # Determinar o Python do venv
    if sys.platform == "win32":
        python_venv = venv_path / "Scripts" / "python.exe"
    else:
        python_venv = venv_path / "bin" / "python"
    
    if not python_venv.exists():
        print(f"{RED}Erro: Python do ambiente virtual não encontrado{NC}")
        sys.exit(1)
    
    return str(python_venv)


def check_model():
    """Verifica se existe um modelo treinado"""
    models_dir = Path("models")
    if not models_dir.exists() or not list(models_dir.glob("*.tar.gz")):
        print(f"{YELLOW}Nenhum modelo encontrado. Treinando modelo...{NC}")
        python_venv = check_venv()
        subprocess.run([python_venv, "-m", "rasa", "train"], check=True)
        print(f"{GREEN}✓ Modelo treinado{NC}")


def process_credentials_file():
    """Processa o arquivo credentials.yml substituindo variáveis de ambiente"""
    credentials_path = Path("credentials.yml")
    credentials_processed_path = Path("credentials.yml.processed")
    
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


def main():
    """Função principal"""
    print(f"{GREEN}========================================{NC}")
    print(f"{GREEN}  Iniciando Servidores do Rasa{NC}")
    print(f"{GREEN}========================================{NC}")
    
    # Verificar se estamos no diretório correto
    if not Path("config.yml").exists():
        print(f"{RED}Erro: Execute este script no diretório chatbot_rasa{NC}")
        print("Exemplo: cd ~/TCC-ChatBotAcademico/chatbot_rasa && python3 start_rasa.py")
        sys.exit(1)
    
    # Carregar variáveis de ambiente do arquivo .env
    env_path = Path(".env")
    if env_path.exists():
        load_dotenv(env_path)
        print(f"{GREEN}✓ Variáveis de ambiente carregadas do .env{NC}")
    else:
        print(f"{YELLOW}⚠ Aviso: Arquivo .env não encontrado{NC}")
        print(f"{YELLOW}  As variáveis de ambiente devem estar configuradas no sistema{NC}")
    
    # Validar variáveis obrigatórias do Telegram
    required_vars = ["TELEGRAM_ACCESS_TOKEN", "TELEGRAM_VERIFY", "TELEGRAM_WEBHOOK_URL"]
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    if missing_vars:
        print(f"{RED}Erro: Variáveis de ambiente obrigatórias não encontradas:{NC}")
        for var in missing_vars:
            print(f"{RED}  - {var}{NC}")
        print(f"\n{YELLOW}Por favor, configure o arquivo .env com as seguintes variáveis:{NC}")
        print(f"{YELLOW}  TELEGRAM_ACCESS_TOKEN=seu-token-aqui{NC}")
        print(f"{YELLOW}  TELEGRAM_VERIFY=seu-verify-aqui{NC}")
        print(f"{YELLOW}  TELEGRAM_WEBHOOK_URL=https://seu-webhook-aqui{NC}")
        print(f"\n{YELLOW}Você pode copiar o arquivo .env.example para .env como template.{NC}")
        sys.exit(1)
    
    # Verificar e preparar ambiente
    python_venv = check_venv()
    check_model()
    
    # Processar arquivo credentials.yml substituindo variáveis de ambiente
    processed_credentials = process_credentials_file()
    if processed_credentials:
        credentials_file = processed_credentials
        print(f"{GREEN}✓ Arquivo credentials.yml processado{NC}")
    else:
        credentials_file = "credentials.yml"
    
    # Preparar ambiente para subprocessos (incluindo variáveis do .env)
    env = os.environ.copy()
    
    # Iniciar servidor de Actions
    print(f"\n{GREEN}[1/2] Iniciando servidor de Actions (porta 5055)...{NC}")
    actions_process = subprocess.Popen(
        [python_venv, "-m", "rasa", "run", "actions"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        universal_newlines=True,
        env=env
    )
    processes.append(actions_process)
    
    # Criar thread para ler logs do servidor de Actions
    def log_actions():
        try:
            for line in iter(actions_process.stdout.readline, ''):
                if line:
                    print(f"{CYAN}[ACTIONS]{NC} {line.rstrip()}")
            actions_process.stdout.close()
        except Exception as e:
            print(f"{RED}Erro ao ler logs de Actions: {e}{NC}")
    
    actions_log_thread = threading.Thread(target=log_actions, daemon=True)
    actions_log_thread.start()
    
    # Aguardar um pouco para o servidor iniciar
    time.sleep(3)
    
    # Verificar se o processo ainda está rodando
    if actions_process.poll() is not None:
        print(f"{RED}Erro ao iniciar servidor de Actions{NC}")
        cleanup()
        sys.exit(1)
    
    print(f"{GREEN}✓ Servidor de Actions iniciado (PID: {actions_process.pid}){NC}")
    
    # Iniciar servidor principal
    print(f"\n{GREEN}[2/2] Iniciando servidor principal do Rasa (porta 5005)...{NC}")
    print(f"{YELLOW}Pressione Ctrl+C para parar ambos os servidores{NC}")
    print(f"{GREEN}========================================{NC}\n")
    
    server_process = subprocess.Popen(
        [python_venv, "-m", "rasa", "run", "-m", "models", 
         "--enable-api", "--cors", "*", "--credentials", credentials_file],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        universal_newlines=True,
        env=env
    )
    processes.append(server_process)
    
    # Criar thread para ler logs do servidor principal
    def log_server():
        try:
            for line in iter(server_process.stdout.readline, ''):
                if line:
                    print(f"{GREEN}[RASA]{NC} {line.rstrip()}")
            server_process.stdout.close()
        except Exception as e:
            print(f"{RED}Erro ao ler logs do servidor Rasa: {e}{NC}")
    
    server_log_thread = threading.Thread(target=log_server, daemon=True)
    server_log_thread.start()
    
    try:
        # Aguardar o processo principal
        server_process.wait()
    except KeyboardInterrupt:
        pass
    finally:
        cleanup()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        cleanup()
    except Exception as e:
        print(f"{RED}Erro: {e}{NC}")
        cleanup()
        sys.exit(1)


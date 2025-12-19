#!/usr/bin/env python3

## Script para criar os arquivos .env e .env.example ##
## Execute: python3 setup_env.py ##


import os
from pathlib import Path

# Conteúdo do arquivo .env
ENV_CONTENT = """# ============================================
# Configurações do Telegram para Rasa
# ============================================
# ⚠️ IMPORTANTE: Este arquivo contém informações sensíveis
# NUNCA compartilhe este arquivo ou faça commit no repositório

# Token de acesso do bot do Telegram
# Obtenha este token criando um bot com @BotFather no Telegram
TELEGRAM_ACCESS_TOKEN=8309691579:AAED-SjbFO6WcjOO75muLKt-_kaPwnTSyog

# String de verificação do webhook
# Pode ser qualquer string, mas deve ser única e segura
TELEGRAM_VERIFY=UnipChatBot

# URL do webhook do Telegram
# Esta URL deve apontar para o endpoint do Rasa
# Exemplo com ngrok: https://<seu-ngrok-id>.ngrok-free.app/webhooks/telegram/webhook
TELEGRAM_WEBHOOK_URL=https://afeec5877954.ngrok-free.app/webhooks/telegram/webhook
"""

# Conteúdo do arquivo .env.example
ENV_EXAMPLE_CONTENT = """# ============================================
# Configurações do Telegram para Rasa
# ============================================
# ⚠️ IMPORTANTE: Copie este arquivo para .env e preencha com seus valores reais
# NUNCA compartilhe o arquivo .env ou faça commit no repositório

# Token de acesso do bot do Telegram
# Obtenha este token criando um bot com @BotFather no Telegram
TELEGRAM_ACCESS_TOKEN=seu-token-aqui

# String de verificação do webhook
# Pode ser qualquer string, mas deve ser única e segura
TELEGRAM_VERIFY=seu-verify-aqui

# URL do webhook do Telegram
# Esta URL deve apontar para o endpoint do Rasa
# Exemplo com ngrok: https://<seu-ngrok-id>.ngrok-free.app/webhooks/telegram/webhook
TELEGRAM_WEBHOOK_URL=https://seu-ngrok-id.ngrok-free.app/webhooks/telegram/webhook
"""


def main():
    """Cria os arquivos .env e .env.example"""
    script_dir = Path(__file__).parent
    
    # Criar arquivo .env
    env_path = script_dir / ".env"
    if env_path.exists():
        print("⚠️  Arquivo .env já existe. Pulando criação...")
    else:
        try:
            with open(env_path, "w", encoding="utf-8") as f:
                f.write(ENV_CONTENT)
            print("✓ Arquivo .env criado com sucesso!")
        except Exception as e:
            print(f"❌ Erro ao criar .env: {e}")
            return False
    
    # Criar arquivo .env.example
    env_example_path = script_dir / ".env.example"
    try:
        with open(env_example_path, "w", encoding="utf-8") as f:
            f.write(ENV_EXAMPLE_CONTENT)
        print("✓ Arquivo .env.example criado com sucesso!")
    except Exception as e:
        print(f"❌ Erro ao criar .env.example: {e}")
        return False
    
    print("\n✅ Configuração concluída!")
    print("\n📝 Próximos passos:")
    print("   1. Verifique o arquivo .env e ajuste os valores se necessário")
    print("   2. Execute: python3 start_rasa.py")
    return True


if __name__ == "__main__":
    main()


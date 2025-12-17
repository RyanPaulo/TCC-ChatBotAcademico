from supabase import create_client, Client
from src.config import settings

# Inicializa o cliente Supabase
supabase: Client = create_client(
    settings.SUPABASE_URL,
    settings.SUPABASE_SERVICE_KEY
)



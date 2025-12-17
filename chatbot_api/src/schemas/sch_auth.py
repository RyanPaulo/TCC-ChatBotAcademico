from pydantic import BaseModel, EmailStr
from typing import Optional

### Esquema de dados 'Aluno' ###

class UserLoginSchema(BaseModel):
    email: EmailStr
    password: str

### Esquema para autenticação via chatbot (RA parcial) ###
class ChatbotAuthRequest(BaseModel):
    email: EmailStr
    ra_resposta: str  # Resposta parcial do RA (ex: "1234" para primeiros 4 dígitos, "5" para último dígito)
    tipo_pergunta: str  # Tipo de pergunta: "primeiros", "ultimos", "digito_posicao", "completo"
    quantidade_digitos: Optional[int] = None  # Quantidade de dígitos (para primeiros/últimos)
    posicao: Optional[int] = None  # Posição do dígito (para digito_posicao, 1-indexed)

class ChatbotAuthResponse(BaseModel):
    success: bool
    message: str
    access_token: Optional[str] = None
    user: Optional[dict] = None
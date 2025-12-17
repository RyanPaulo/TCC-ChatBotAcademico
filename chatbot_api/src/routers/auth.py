
from fastapi import APIRouter, HTTPException, status
from src.supabase_client import supabase
from src.schemas.sch_auth import UserLoginSchema, ChatbotAuthRequest, ChatbotAuthResponse
from ..config import settings
from datetime import datetime, timedelta
import jwt

router = APIRouter(
    prefix="/auth",
    tags=["Autenticação"]
)

### ENDPOINT PARA AUTENTICAÇÃO DO USUARIO ###
@router.post("/login", status_code=status.HTTP_200_OK)
def user_login(credentials: UserLoginSchema):

    try:
        # Chama a função de login nativa do Supabase
        response = supabase.auth.sign_in_with_password({
            "email": credentials.email,
            "password": credentials.password
        })

        # Usar o access_token da sessão para buscar os dados completos do usuário.
        user_data_response = supabase.auth.get_user(response.session.access_token)

        user_metadata = user_data_response.user.user_metadata
        user_name = user_metadata.get("name", None)
        user_role = user_metadata.get("role", "anonimo")


        # Se o login for bem-sucedido, o Supabase retorna os dados da sessão
        return {
            "message": "Login realizado com sucesso!",
            "access_token": response.session.access_token,
            "user": {
                "id": response.user.id,
                "email": response.user.email,
                "name": user_name,
                "role": user_role
            }
        }

    except Exception as e:
        # Captura erros de login (e-mail não existe, senha incorreta, etc.)
        # O Supabase geralmente retorna um erro específico que podemos tratar
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Erro de autenticação: As credenciais são inválidas."
        )


### FUNÇÃO AUXILIAR PARA VALIDAR RA PARCIAL ###
def _validar_ra_parcial(ra_completo: str, ra_resposta: str, tipo_pergunta: str, quantidade_digitos: int = None, posicao: int = None) -> bool:
    """
    Valida uma resposta parcial do RA baseado no tipo de pergunta.
    
    Args:
        ra_completo: RA completo do aluno
        ra_resposta: Resposta fornecida pelo usuário
        tipo_pergunta: Tipo de pergunta ("primeiros", "ultimos", "digito_posicao", "completo")
        quantidade_digitos: Quantidade de dígitos (para primeiros/últimos)
        posicao: Posição do dígito (para digito_posicao, 1-indexed)
    
    Returns:
        True se a resposta estiver correta, False caso contrário
    """
    ra_completo = ra_completo.strip()
    ra_resposta = ra_resposta.strip()
    
    if tipo_pergunta == "primeiros":
        if quantidade_digitos is None:
            quantidade_digitos = len(ra_resposta)
        return ra_completo[:quantidade_digitos] == ra_resposta
    
    elif tipo_pergunta == "ultimos":
        if quantidade_digitos is None:
            quantidade_digitos = len(ra_resposta)
        return ra_completo[-quantidade_digitos:] == ra_resposta
    
    elif tipo_pergunta == "digito_posicao":
        if posicao is None:
            return False
        # Posição 1-indexed, então subtrai 1 para indexar
        if posicao < 1 or posicao > len(ra_completo):
            return False
        # Comparar em maiúsculas para evitar problemas de case sensitivity
        return ra_completo.upper()[posicao - 1] == ra_resposta.upper()
    
    elif tipo_pergunta == "completo":
        return ra_completo == ra_resposta
    
    return False


### ENDPOINT PARA AUTENTICAÇÃO VIA CHATBOT (RA PARCIAL) ###
@router.post("/chatbot-login", status_code=status.HTTP_200_OK, response_model=ChatbotAuthResponse)
def chatbot_login(auth_request: ChatbotAuthRequest):
    """
    Endpoint para autenticação via chatbot usando validação parcial do RA.
    
    O Rasa pode fazer perguntas aleatórias sobre o RA do aluno e validar a resposta aqui.
    Se a validação for bem-sucedida, retorna um token JWT customizado para o chatbot.
    """
    try:
        # 1. Buscar o aluno pelo email
        aluno_response = supabase.table("aluno").select("*").eq("email_institucional", auth_request.email).single().execute()
        
        if not aluno_response.data:
            return ChatbotAuthResponse(
                success=False,
                message="Aluno não encontrado com este e-mail."
            )
        
        aluno = aluno_response.data
        ra_completo = aluno.get("matricula_ra", "")
        
        if not ra_completo:
            return ChatbotAuthResponse(
                success=False,
                message="RA não encontrado para este aluno."
            )
        
        # 2. Validar a resposta parcial do RA
        ra_valido = _validar_ra_parcial(
            ra_completo=ra_completo,
            ra_resposta=auth_request.ra_resposta,
            tipo_pergunta=auth_request.tipo_pergunta,
            quantidade_digitos=auth_request.quantidade_digitos,
            posicao=auth_request.posicao
        )
        
        if not ra_valido:
            return ChatbotAuthResponse(
                success=False,
                message="Resposta do RA incorreta. Tente novamente."
            )
        
        # 3. Se a validação for bem-sucedida, gerar token JWT customizado
        # Usa a SUPABASE_SERVICE_KEY como secret (ou pode criar um secret específico para chatbot)
        jwt_secret = settings.SUPABASE_SERVICE_KEY
        
        # Payload do token
        payload = {
            "user_id": str(aluno.get("id")),
            "email": auth_request.email,
            "role": "aluno",
            "chatbot_auth": True,  # Indica que é autenticação via chatbot
            "exp": datetime.utcnow() + timedelta(hours=24),  # Token válido por 24 horas
            "iat": datetime.utcnow()
        }
        
        # Gerar token JWT
        try:
            access_token = jwt.encode(payload, jwt_secret, algorithm="HS256")
        except Exception as jwt_error:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Erro ao gerar token: {str(jwt_error)}"
            )
        
        # 4. Retornar resposta de sucesso com token
        return ChatbotAuthResponse(
            success=True,
            message="Autenticação realizada com sucesso!",
            access_token=access_token,
            user={
                "id": str(aluno.get("id")),
                "email": auth_request.email,
                "nome": f"{aluno.get('nome_aluno', '')} {aluno.get('sobrenome_aluno', '')}".strip(),
                "matricula_ra": aluno.get("matricula_ra"),
                "role": "aluno"
            }
        )
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao processar autenticação: {str(e)}"
        )


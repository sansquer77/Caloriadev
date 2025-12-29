"""
Módulo de autenticação e segurança.
Gerencia tokens JWT e hashing de senhas.
"""

import jwt
import datetime
import os
import secrets
from typing import Optional
from werkzeug.security import generate_password_hash, check_password_hash

# Constantes de segurança
TOKEN_ALGORITHM = "HS256"
DEFAULT_TOKEN_EXPIRY_MINUTES = 60 * 24  # 24 horas
MIN_PASSWORD_LENGTH = 6

# Cache da secret key para evitar múltiplas chamadas ao ambiente
_secret_key_cache: Optional[str] = None


def get_secret_key() -> str:
    """
    Retorna a secret key do ambiente com cache.
    Em desenvolvimento, gera uma chave temporária (não recomendado em produção).
    """
    global _secret_key_cache
    
    if _secret_key_cache:
        return _secret_key_cache
    
    secret_key = os.getenv('SECRET_KEY')
    
    if not secret_key:
        # Em desenvolvimento, gerar uma chave temporária
        if os.getenv('ENVIRONMENT', 'development') == 'development':
            secret_key = secrets.token_hex(32)
            print("⚠️ AVISO: SECRET_KEY não definida. Usando chave temporária (não use em produção).")
        else:
            raise EnvironmentError(
                "A variável de ambiente SECRET_KEY não está definida. "
                "Configure-a antes de executar em produção."
            )
    
    _secret_key_cache = secret_key
    return secret_key


def validate_password_strength(password: str) -> tuple[bool, str]:
    """
    Valida força da senha.
    Retorna (válido, mensagem de erro).
    """
    if len(password) < MIN_PASSWORD_LENGTH:
        return False, f"Senha deve ter pelo menos {MIN_PASSWORD_LENGTH} caracteres."
    return True, ""


def create_password_hash(password: str) -> str:
    """
    Gera hash seguro para senha usando Werkzeug (PBKDF2).
    """
    return generate_password_hash(password, method='pbkdf2:sha256:600000')


def verify_password_hash(hash_: str, password: str) -> bool:
    """
    Verifica senha contra hash de forma segura.
    Usa comparação em tempo constante para prevenir timing attacks.
    """
    if not hash_ or not password:
        return False
    return check_password_hash(hash_, password)


def generate_token(user_id: int, expires_minutes: int = DEFAULT_TOKEN_EXPIRY_MINUTES) -> str:
    """
    Gera token JWT para autenticação.
    
    Args:
        user_id: ID do usuário
        expires_minutes: Tempo de expiração em minutos
    
    Returns:
        Token JWT codificado
    """
    now = datetime.datetime.utcnow()
    payload = {
        'sub': user_id,
        'iat': now,
        'exp': now + datetime.timedelta(minutes=expires_minutes),
        'type': 'access'
    }
    return jwt.encode(payload, get_secret_key(), algorithm=TOKEN_ALGORITHM)


def decode_token(token: str) -> Optional[int]:
    """
    Decodifica token JWT e retorna user_id se válido.
    
    Args:
        token: Token JWT a decodificar
    
    Returns:
        user_id se válido, None caso contrário
    """
    if not token:
        return None
    
    try:
        payload = jwt.decode(token, get_secret_key(), algorithms=[TOKEN_ALGORITHM])
        return payload.get('sub')
    except jwt.ExpiredSignatureError:
        print("Token expirado")
        return None
    except jwt.InvalidTokenError as e:
        print(f"Token inválido: {e}")
        return None

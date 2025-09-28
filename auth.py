import jwt
import datetime
import os
from typing import Optional
from werkzeug.security import generate_password_hash, check_password_hash
from flask import request

def get_secret_key() -> str:
    """
    Retorna a secret key do ambiente.
    Erra de forma explícita caso não esteja definida para segurança máxima.
    """
    secret_key = os.getenv('SECRET_KEY')
    if not secret_key:
        raise EnvironmentError("A variável de ambiente SECRET_KEY não está definida.")
    return secret_key

def create_password_hash(password: str) -> str:
    """Gera hash seguro para senha."""
    return generate_password_hash(password)

def verify_password_hash(hash_: str, password: str) -> bool:
    """Verifica senha contra hash."""
    return check_password_hash(hash_, password)

def generate_token(user_id: int, expires_minutes: int = 30) -> str:
    """Gera token JWT para autenticação."""
    payload = {
        'sub': user_id,
        'iat': datetime.datetime.utcnow(),
        'exp': datetime.datetime.utcnow() + datetime.timedelta(minutes=expires_minutes)
    }
    token = jwt.encode(payload, get_secret_key(), algorithm="HS256")
    return token

def decode_token(token: str) -> Optional[int]:
    """Decodifica token JWT e retorna user_id se válido."""
    try:
        payload = jwt.decode(token, get_secret_key(), algorithms=["HS256"])
        return payload['sub']
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
        return None

def get_token_from_header() -> Optional[str]:
    """Pega token do header Authorization Bearer."""
    auth_header = request.headers.get('Authorization', None)
    if auth_header and auth_header.startswith('Bearer '):
        return auth_header.split(' ')[1]
    return None

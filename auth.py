import jwt
from datetime import datetime, timedelta
from errors import HttpError

JWT_SECRET = "secret-key"
JWT_ALGORITHM = "HS256"


def create_jwt_token(user_id: int) -> str:
    payload = {
        'user_id': user_id,
        'exp': datetime.utcnow() + timedelta(hours=24),
        'iat': datetime.utcnow()
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_jwt_token(token: str) -> dict:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HttpError(401, "Token expired")
    except jwt.InvalidTokenError:
        raise HttpError(401, "Invalid token")
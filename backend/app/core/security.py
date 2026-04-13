import uuid
from datetime import datetime, timedelta, timezone
from jose import JWTError, jwt
from passlib.context import CryptContext
from app.config import settings

# bcrypt 密码上下文
_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(plain_password: str) -> str:
    """对明文密码进行 bcrypt 哈希"""
    return _pwd_context.hash(plain_password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """验证明文密码是否与哈希匹配"""
    return _pwd_context.verify(plain_password, hashed_password)


def create_access_token(subject: str | int, role: str) -> str:
    """生成 JWT Access Token，payload 中包含唯一 jti 用于登出黑名单"""
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.jwt_access_token_expire_minutes
    )
    payload = {
        "sub": str(subject),
        "role": role,
        "exp": expire,
        "jti": str(uuid.uuid4()),  # JWT ID，用于 token 黑名单
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict:
    """解码并验证 JWT，返回 payload；失败抛出 JWTError"""
    return jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])


def create_refresh_token(user_id: int) -> tuple[str, str]:
    """生成 Refresh Token，返回 (token_str, jti)

    jti 用于在 Redis 中存储，实现单次使用（旋转刷新）。
    """
    jti = str(uuid.uuid4())
    expire = datetime.now(timezone.utc) + timedelta(days=settings.jwt_refresh_token_expire_days)
    payload = {
        "sub": str(user_id),
        "type": "refresh",
        "exp": expire,
        "jti": jti,
    }
    token = jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
    return token, jti


def decode_refresh_token(token: str) -> dict:
    """解码并验证 Refresh Token；失败抛出 JWTError。

    额外校验 type 字段，防止 access token 冒充 refresh token。
    """
    payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    if payload.get("type") != "refresh":
        raise JWTError("不是有效的 Refresh Token")
    return payload

from functools import lru_cache
from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # 数据库配置
    db_host: str = "localhost"
    db_port: int = 3306
    db_user: str = "root"
    db_password: str = ""
    db_name: str = "drug_ocr_db"

    # JWT 配置
    jwt_secret_key: str = "change_me_in_production"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 60       # Access Token 有效期（分钟）
    jwt_refresh_token_expire_days: int = 7          # Refresh Token 有效期（天）

    # SMTP 邮件配置（阿里云）
    smtp_host: str = "smtpdm.aliyun.com"
    smtp_port: int = 465
    smtp_user: str = ""          # 发件人邮箱地址（阿里云 SMTP 账号）
    smtp_password: str = ""      # SMTP 授权码
    smtp_from: str = ""          # 发件人显示名+地址，如 "药品管理系统 <noreply@example.com>"
    smtp_use_ssl: bool = True    # 阿里云 465 端口需 SSL

    # 前端域名（用于邮件中的重置密码链接）
    frontend_url: str = "http://localhost:5173"

    # Redis 配置（token 黑名单 + 登录限流）
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0
    redis_password: str = ""

    # 首次启动自动创建管理员
    initial_admin_username: str = "admin"
    initial_admin_password: str = "Admin@2026!"
    initial_admin_real_name: str = "系统管理员"

    # 登录限流配置
    login_max_failures: int = 5
    login_lockout_minutes: int = 15

    # 阿里云百炼 qwen-vl-ocr OCR 配置
    dashscope_api_key: str = ""
    qwen_ocr_model: str = "qwen-vl-ocr-latest"
    qwen_ocr_timeout_seconds: int = 120
    qwen_ocr_max_attempts: int = 2
    qwen_ocr_max_pixels: int = 2097152
    qwen_ocr_per_record_concurrency: int = 2
    qwen_ocr_global_concurrency: int = 3
    max_ocr_images_per_record: int = 6

    # 阿里云 OSS 临时签名 URL：Qwen OCR 图片传输统一使用该链路
    aliyun_oss_endpoint: str = ""
    aliyun_oss_bucket: str = ""
    aliyun_oss_access_key_id: str = ""
    aliyun_oss_access_key_secret: str = ""
    aliyun_oss_ocr_prefix: str = "ocr/qwen"
    aliyun_oss_signed_url_expire_seconds: int = 1800

    # DeepSeek 多图一致性辅助校验（只在无重叠字段时触发）
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-v4-flash"
    deepseek_timeout_seconds: int = 30

    # 文件上传配置
    upload_dir: str = "uploads"
    max_upload_size_mb: int = 10

    # 预警配置
    expiry_warning_days: int = 30
    low_stock_threshold: int = 10

    # 服务配置
    backend_host: str = "0.0.0.0"
    backend_port: int = 8000
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    @model_validator(mode="after")
    def validate_jwt_secret(self) -> "Settings":
        """JWT 密钥强度校验：禁止使用默认值或弱密钥"""
        if self.jwt_secret_key == "change_me_in_production":
            raise ValueError(
                "JWT_SECRET_KEY 不能使用默认值！\n"
                "请在 .env 中配置随机强密钥：\n"
                "  python -c \"import secrets; print(secrets.token_urlsafe(48))\""
            )
        if len(self.jwt_secret_key) < 32:
            raise ValueError(
                "JWT_SECRET_KEY 长度不能少于 32 个字符，当前长度过短，存在安全风险。"
            )
        return self

    @property
    def database_url(self) -> str:
        # aiomysql 异步驱动
        return (
            f"mysql+aiomysql://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
            f"?charset=utf8mb4"
        )

    @property
    def redis_url(self) -> str:
        if self.redis_password:
            return f"redis://:{self.redis_password}@{self.redis_host}:{self.redis_port}/{self.redis_db}"
        return f"redis://{self.redis_host}:{self.redis_port}/{self.redis_db}"

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",")]

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",   # 容忍 .env 中未声明的多余键，避免旧配置残留导致启动失败
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

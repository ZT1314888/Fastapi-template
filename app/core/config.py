from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Environment configuration
    ENV: str = "development"  # Default value is "development"

    # Basic configuration
    PROJECT_NAME: str = "FastAPI Template"
    API_V1_STR: str = "/api/v1"
    API_PORT: int = 8001

    # Docker port configuration (optional, for docker-compose)
    REDIS_EXTERNAL_PORT: int = 6386
    NGINX_HTTP_PORT: int = 8086
    NGINX_HTTPS_PORT: int = 8446
    FLOWER_PORT: int = 5556

    # Database configuration
    POSTGRES_USER: str = "demo"
    POSTGRES_PASSWORD: str = "demo123"
    POSTGRES_HOST: str = "192.168.110.90"
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str = "demo"

    # Redis configuration
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_PASSWORD: str = ""

    # Celery configuration
    CELERY_BROKER_URL: str = ""  # Will be set in __init__
    CELERY_RESULT_BACKEND: str = ""  # Will be set in __init__

    # HTTP proxy configuration - only used in test environment
    USE_HTTP_PROXY: bool = False  # Default not to use proxy
    HTTP_PROXY: str = "http://127.0.0.1:7890"
    HTTPS_PROXY: str = "http://127.0.0.1:7890"

    # Email configuration
    MAIL_MAILER: str = "smtp"
    MAIL_HOST: str = "localhost"
    MAIL_PORT: int = 1025
    MAIL_USERNAME: str = "user"
    MAIL_PASSWORD: str = "password"
    MAIL_FROM_ADDRESS: str = "noreply@example.com"
    MAIL_FROM_NAME: str = "Seiki"
    MAIL_ENCRYPTION: str = "none"

    # Brevo configuration
    BREVO_API_KEY: str = "dummy-api-key"
    BREVO_EMAIL_FROM: str = "noreply@example.com"
    BREVO_EMAIL_FROM_NAME: str = "Seiki"

    # Administrator email
    ADMIN_EMAIL: str = "dev@zetos.fr"

    # JWT configuration
    SECRET_KEY: str = "your-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # S3 configuration
    AWS_ACCESS_KEY_ID: str = "your-access-key"
    AWS_SECRET_ACCESS_KEY: str = "your-secret-key"
    AWS_REGION: str = "us-east-1"
    AWS_BUCKET_NAME: str = "your-bucket-name"
    AWS_ENDPOINT: str = "https://s3.amazonaws.com"

    # Google OAuth configuration (ID Token verification)
    GOOGLE_CLIENT_ID: str = ""

    # Frontend URL configuration
    FRONTEND_URL: str = "http://localhost:3000"
    PASSWORD_RESET_URL_TEMPLATE: str = "{frontend_url}/reset-password?token={token}"

    # Verification code configuration
    VERIFICATION_CODE_LENGTH: int = 6
    VERIFICATION_CODE_EXPIRE_SECONDS: int = 300  # 5 minutes
    VERIFICATION_CODE_COOLDOWN_SECONDS: int = 60  # 60 seconds cooldown

    # Password reset configuration
    PASSWORD_RESET_TOKEN_EXPIRE_MINUTES: int = 30

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"  # Optional, specify encoding

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Now set Celery URLs after all attributes are loaded from env
        if self.REDIS_PASSWORD:
            redis_url = (
                f"redis://:{self.REDIS_PASSWORD}@{self.REDIS_HOST}:{self.REDIS_PORT}/0"
            )
        else:
            redis_url = f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/0"
        self.CELERY_BROKER_URL = redis_url
        self.CELERY_RESULT_BACKEND = redis_url


settings = Settings()

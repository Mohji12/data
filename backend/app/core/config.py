import os
from functools import lru_cache
from pathlib import Path
from urllib.parse import quote_plus

from dotenv import load_dotenv

# Load mock_test/backend/.env before reading os.environ (uvicorn cwd may vary).
load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env")


class Settings:
    def __init__(self) -> None:
        self.db_host: str = "3.7.74.62"
        self.db_port: int = 3306
        self.db_user: str = "admin"
        self.db_password: str = "HarishCC@2026SecureDB"
        self.db_name: str = "admin_CriticalCareClasses"
        # If false: only verify login; never UPDATE users.password (PHP owns the 32-char hash).
        # If true: after successful login, rewrite password column to Python-computed PHP-outer hash.
        self.auth_sync_password_on_login: bool = os.getenv(
            "AUTH_SYNC_PASSWORD_ON_LOGIN", ""
        ).lower() in ("1", "true", "yes")
        # LOCAL TESTING ONLY: when true, admin users API can expose decrypted/plaintext password fields.
        # Keep false in production.
        self.admin_expose_plaintext_password: bool = os.getenv(
            "ADMIN_EXPOSE_PLAINTEXT_PASSWORD", "false"
        ).lower() in ("1", "true", "yes")
        # When true, email-only login requires payment_status=Credit and approve=1 (like PHP site).
        # Set to false for internal/mock use where any existing user email is enough.
        self.email_only_login_strict: bool = os.getenv(
            "EMAIL_ONLY_LOGIN_STRICT", "true"
        ).lower() in ("1", "true", "yes")
        self.api_token_secret: str = os.getenv(
            "API_TOKEN_SECRET",
            "critical-care-classes-fastapi-secret",
        )
        self.api_token_ttl_hours: int = int(os.getenv("API_TOKEN_TTL_HOURS", "24"))
        # Comma-separated browser origins allowed for cross-origin API calls (frontend host).
        _cors = os.getenv("CORS_ORIGINS", "").strip()
        if _cors:
            self.cors_origins: list[str] = [o.strip().rstrip("/") for o in _cors.split(",") if o.strip()]
        else:
            self.cors_origins = [
                "https://harishcriticalcareclasses.com",
                "https://www.harishcriticalcareclasses.com",
                "http://localhost:8080",
                "http://127.0.0.1:8080",
            ]
        self.payment_gateway_name: str = os.getenv("PAYMENT_GATEWAY_NAME", "razorpay")
        self.payment_key_id: str = os.getenv("PAYMENT_KEY_ID", "")
        self.payment_key_secret: str = os.getenv("PAYMENT_KEY_SECRET", "")
        self.payment_webhook_secret: str = os.getenv("PAYMENT_WEBHOOK_SECRET", "")
        # Create registration_payment_txn on startup if missing (legacy DBs from PHP only).
        self.auto_create_registration_txn_table: bool = os.getenv(
            "AUTO_CREATE_REGISTRATION_TXN_TABLE", "true"
        ).lower() in ("1", "true", "yes")
        self.smtp_host: str = os.getenv("SMTP_HOST", "")
        self.smtp_port: int = int(os.getenv("SMTP_PORT", "587"))
        self.smtp_username: str = os.getenv("SMTP_USERNAME", "")
        self.smtp_password: str = os.getenv("SMTP_PASSWORD", "")
        self.smtp_from: str = os.getenv("SMTP_FROM", self.smtp_username)
        # Comma-separated addresses (matches PHP CC_EMAIL / BCC_EMAIL for thank-you and bulk mail).
        self.smtp_cc: str = os.getenv("SMTP_CC", "").strip()
        self.smtp_bcc: str = os.getenv("SMTP_BCC", "").strip()
        self.smtp_reply_to: str = os.getenv("SMTP_REPLY_TO", "").strip()
        # Used in legacy PHP email views (<?=APP_NAME?>, plain thank-you body).
        self.email_app_name: str = os.getenv("EMAIL_APP_NAME", "Online Master Classes").strip()
        # Base URL for <?=resources_url()?> in copied PHP templates (logo, etc.). No trailing slash.
        _asset = os.getenv("EMAIL_ASSET_BASE_URL", "").strip().rstrip("/")
        self.email_asset_base_url: str = _asset or "https://harishcriticalcareclasses.com"
        _logo = os.getenv("EMAIL_LOGO_URL", "").strip()
        self.email_logo_url: str = _logo or f"{self.email_asset_base_url}/hero/logo.png"
        # Root folder containing PHP views: application/views/email_template (override if repo layout differs).
        _default_tpl = Path(__file__).resolve().parents[4] / "application" / "views" / "email_template"
        self.email_template_php_root: str = os.getenv(
            "EMAIL_TEMPLATE_PHP_ROOT", str(_default_tpl)
        ).strip()
        # Public site base URL (no trailing slash) for legacy PHP uploads, e.g. https://harishcriticalcareclasses.com
        # Used to build /upload/user/document_file/{filename} links in admin user list/detail.
        # Default matches public site / email assets so admin document links work without extra .env.
        _legacy = os.getenv("LEGACY_UPLOAD_BASE_URL", "").strip().rstrip("/")
        self.legacy_upload_base_url: str = _legacy or self.email_asset_base_url
        # FastAPI public base for locally stored registration uploads (admin "View document").
        _api_public = os.getenv("API_PUBLIC_BASE_URL", "").strip().rstrip("/")
        self.api_public_base_url: str = _api_public or "http://127.0.0.1:8000"
        # S3 user documents (registration uploads). Prefer AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY in .env (never commit).
        self.aws_access_key_id: str = os.getenv("AWS_ACCESS_KEY_ID", "").strip()
        self.aws_secret_access_key: str = os.getenv("AWS_SECRET_ACCESS_KEY", "").strip()
        self.s3_bucket_name: str = os.getenv("S3_BUCKET_NAME", "").strip()
        self.s3_region: str = (
            os.getenv("AWS_REGION", os.getenv("S3_REGION", "ap-south-1")).strip() or "ap-south-1"
        )
        self.s3_user_prefix: str = (os.getenv("S3_USER_PREFIX", "user").strip().strip("/") or "user")
        self.s3_presign_expires_seconds: int = int(os.getenv("S3_PRESIGN_EXPIRES_SEC", "86400"))
        # If "public-read", objects are world-readable and upload returns an https URL to store in DB; leave empty for private + presigned admin links.
        self.s3_object_acl: str = os.getenv("S3_OBJECT_ACL", "").strip()
        # Meta WhatsApp Cloud API (server-side only).
        self.whatsapp_api_key: str = os.getenv("WHATSAPP_API_KEY", "").strip()
        self.whatsapp_phone_number_id: str = os.getenv("WHATSAPP_PHONE_NUMBER_ID", "").strip()
        self.whatsapp_api_base: str = os.getenv(
            "WHATSAPP_API_BASE",
            "https://graph.facebook.com/v20.0",
        ).strip().rstrip("/")
        self.whatsapp_batch_size: int = max(1, int(os.getenv("WHATSAPP_BATCH_SIZE", "25")))
        self.whatsapp_send_delay_ms: int = max(0, int(os.getenv("WHATSAPP_SEND_DELAY_MS", "100")))
        self.whatsapp_send_max_retries: int = max(0, int(os.getenv("WHATSAPP_SEND_MAX_RETRIES", "1")))
        self.whatsapp_send_timeout_sec: int = max(1, int(os.getenv("WHATSAPP_SEND_TIMEOUT_SEC", "15")))

    @property
    def sqlalchemy_database_uri(self) -> str:
        user = self.db_user
        # URL‑encode the password so '@' and other symbols are safe in the URL
        password = quote_plus(self.db_password)
        host = self.db_host
        port = self.db_port
        name = self.db_name
        return f"mysql+pymysql://{user}:{password}@{host}:{port}/{name}"


@lru_cache
def get_settings() -> Settings:
    return Settings()
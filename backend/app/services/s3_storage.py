from __future__ import annotations

import mimetypes
import uuid
from urllib.parse import quote, unquote, urlparse
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from app.core.config import Settings


def s3_uploads_enabled(s: "Settings") -> bool:
    return bool(s.s3_bucket_name and s.s3_region)


def _s3_client(s: "Settings"):
    import boto3

    kwargs: dict = {"region_name": s.s3_region}
    if s.aws_access_key_id and s.aws_secret_access_key:
        kwargs["aws_access_key_id"] = s.aws_access_key_id
        kwargs["aws_secret_access_key"] = s.aws_secret_access_key
    return boto3.client("s3", **kwargs)


def guess_content_type(suffix: str) -> Optional[str]:
    mt, _ = mimetypes.guess_type(f"x{suffix}")
    return mt or None


def upload_user_document(content: bytes, suffix: str, s: "Settings") -> str:
    """
    Upload bytes under `{s3_user_prefix}/{uuid}{suffix}`.
    Returns either a permanent https URL (if S3_OBJECT_ACL=public-read) or the S3 object key to store in DB.
    """
    key = f"{s.s3_user_prefix}/{uuid.uuid4().hex}{suffix}"
    client = _s3_client(s)
    extra: dict = {"Bucket": s.s3_bucket_name, "Key": key, "Body": content}
    ct = guess_content_type(suffix)
    if ct:
        extra["ContentType"] = ct
    if s.s3_object_acl:
        extra["ACL"] = s.s3_object_acl
    client.put_object(**extra)
    if (s.s3_object_acl or "").lower() == "public-read":
        return f"https://{s.s3_bucket_name}.s3.{s.s3_region}.amazonaws.com/{key}"
    return key


DOC_UPLOAD_PATH = "/upload/user/document_file/"
_MARKETING_DOC_HOSTS = frozenset({"harishcriticalcareclasses.com", "www.harishcriticalcareclasses.com"})


def registration_document_filename(stored: Optional[str]) -> Optional[str]:
    """Plain filename from DB value or from a full /upload/user/document_file/ URL."""
    if not stored or not str(stored).strip():
        return None
    v = str(stored).strip()
    if not v.lower().startswith(("http://", "https://")):
        return v if "/" not in v else None
    try:
        path = urlparse(v).path
        lower = path.lower()
        marker = DOC_UPLOAD_PATH.lower()
        idx = lower.find(marker)
        if idx == -1:
            return None
        name = path[idx + len(DOC_UPLOAD_PATH) :]
        return unquote(name) if name else None
    except Exception:
        return None


def public_registration_document_url(filename: str, s: "Settings", *, api_base: Optional[str] = None) -> Optional[str]:
    fn = (filename or "").strip()
    if not fn:
        return None
    base = (api_base or getattr(s, "api_public_base_url", "") or "").strip().rstrip("/")
    if not base:
        return None
    return f"{base}{DOC_UPLOAD_PATH}{quote(fn, safe='')}"


def presigned_get_url(key: str, s: "Settings") -> Optional[str]:
    if not s3_uploads_enabled(s):
        return None
    try:
        return _s3_client(s).generate_presigned_url(
            "get_object",
            Params={"Bucket": s.s3_bucket_name, "Key": key},
            ExpiresIn=max(60, min(s.s3_presign_expires_seconds, 604800)),
        )
    except Exception:
        return None


def resolve_admin_document_url(
    stored: Optional[str],
    s: "Settings",
    legacy_base: str,
    *,
    api_base: Optional[str] = None,
) -> Optional[str]:
    """
    Build a URL the admin UI can open: full https links, S3 presigned keys,
    local FastAPI /upload/user/document_file/{filename}, or legacy PHP static path.
    """
    if not stored or not str(stored).strip():
        return None
    v = str(stored).strip()
    low = v.lower()
    public_api = (api_base or getattr(s, "api_public_base_url", "") or "").strip().rstrip("/")

    plain = registration_document_filename(v)
    if plain and public_api:
        return public_registration_document_url(plain, s, api_base=public_api)

    if low.startswith("http://") or low.startswith("https://"):
        try:
            host = urlparse(v).hostname or ""
            if host.lower() in _MARKETING_DOC_HOSTS and plain and public_api:
                return public_registration_document_url(plain, s, api_base=public_api)
        except Exception:
            pass
        return v
    if s3_uploads_enabled(s) and "/" in v:
        url = presigned_get_url(v, s)
        if url:
            return url
    if "/" not in v:
        return public_registration_document_url(v, s, api_base=public_api)
    base = (legacy_base or "").strip().rstrip("/")
    if base:
        return f"{base}/upload/user/document_file/{quote(v, safe='')}"
    return None

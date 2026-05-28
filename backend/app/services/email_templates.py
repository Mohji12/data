from __future__ import annotations

import logging
import re
from datetime import datetime
from html import escape
from pathlib import Path

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import BatchMaster, EmailTemplateMaster, Package, User
from app.services.password_crypto import my_simple_crypt

logger = logging.getLogger(__name__)

EMAIL_TEMPLATE_TYPE_REGISTRATION_THANK_YOU = "registration_thank_you"
EMAIL_TEMPLATE_TYPE_DOCUMENT_VERIFIED = "document_verified"
EMAIL_TEMPLATE_TYPE_DOCUMENT_DENIED = "document_denied"

# Same subject string as PHP Register.php (Razorpay / Instamojo success).
REGISTRATION_THANK_YOU_SUBJECT = "Thank you for registration in Online Master Classes"

# Mirrors application/controllers/Register.php Razorpay branch (full elseif chain).
_SUBSCRIPTION_TO_SLUG: dict[str, str] = {
    "Batch 4": "batch_4/thank_you",
    "Batch EDIC 1": "batch_edic_1/thank_you",
    "Batch 5": "batch_5/thank_you",
    "Batch EDIC 2": "batch_edic_2/thank_you",
    "Batch 6": "batch_6/thank_you",
    "Batch EDIC 3": "batch_edic_3/thank_you",
    "Batch 7": "batch_7/thank_you",
    "Batch EDIC 4": "batch_edic_4/thank_you",
    "Batch 8": "batch_8/thank_you",
    "Batch EDIC 5": "batch_edic_5/thank_you",
    "Batch 9": "batch_9/thank_you",
    "CP 1": "cp_1/thank_you",
    "CP 2": "cp_2/thank_you",
    "Batch 10": "batch_10/thank_you",
    "Batch EDIC 6": "batch_edic_6/thank_you",
    "CP 3": "cp_3/thank_you",
    "CP 4": "cp_4/thank_you",
    "Batch 11": "batch_11/thank_you",
    "Batch EDIC 7": "batch_edic_7/thank_you",
    "Batch 12": "batch_12/thank_you",
    "CP 5": "cp_5/thank_you",
    "CP 6": "cp_6/thank_you",
    "Batch EDIC 8": "batch_edic_8/thank_you",
    "Batch 13": "batch_13/thank_you",
    "CCM Batch 1": "ccm_batch_1/thank_you",
    "Batch 14": "batch_14/thank_you",
    "CP 7": "cp_7/thank_you",
    "CP 8": "cp_8/thank_you",
    "Batch EDIC 9": "batch_edic_9/thank_you",
    "CCM Batch 2": "ccm_batch_2/thank_you",
    "Batch 15": "batch_15/thank_you",
    "BATCH 16-MCCM": "batch_15/thank_you",
    "Batch 16": "batch_15/thank_you",
    "CP 9": "cp_8/thank_you",
    "CP 10": "cp_8/thank_you",
    "Batch EDIC 10": "batch_edic_9/thank_you",
    "CCM Batch 3": "ccm_batch_2/thank_you",
    "CCM FOR MEDICINE": "ccm_batch_2/thank_you",
    "EDIC2026": "batch_edic_9/thank_you",
}

_LEGACY_EMAIL_LOGO_PATH = "assets/img/logo.png"


def email_logo_url() -> str:
    """Public HTTPS URL for the logo image embedded in HTML emails."""
    return (get_settings().email_logo_url or "").strip()


def _fix_email_logo_src(html: str) -> str:
    """PHP templates reference legacy /assets/img/logo.png; the React site uses /hero/logo.png."""
    logo = email_logo_url()
    if not logo:
        return html
    asset_base = (get_settings().email_asset_base_url or "").rstrip("/")
    replacements = [
        f"{asset_base}/{_LEGACY_EMAIL_LOGO_PATH}",
        f"{asset_base}{_LEGACY_EMAIL_LOGO_PATH}",
        _LEGACY_EMAIL_LOGO_PATH,
    ]
    for old in replacements:
        html = html.replace(old, logo)
    html = re.sub(
        rf'src=(["\'])(?:https?://[^"\']+/)?{re.escape(_LEGACY_EMAIL_LOGO_PATH)}\1',
        lambda m: f'src={m.group(1)}{logo}{m.group(1)}',
        html,
        flags=re.IGNORECASE,
    )
    return html


def _legacy_php_layout(content: str) -> str:
    settings = get_settings()
    asset_base = (settings.email_asset_base_url or "").rstrip("/")
    logo = email_logo_url()
    app_name = escape(settings.email_app_name)
    return f"""
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
<html xmlns="http://www.w3.org/1999/xhtml">
<head>
    <meta http-equiv="Content-Type" content="text/html; charset=utf-8" />
    <title>{app_name}</title>
</head>
<body style="margin: 0; padding: 0;">
<table border="0" cellpadding="0" cellspacing="0" width="80%" style="margin: auto; border: 1px solid #e1e8ed; font-family: 'Quicksand', sans-serif; color: #333;">
    <tr bgcolor="#1f6798">
        <td colspan="3" width="100%" style="padding: 8px;">&nbsp;</td>
    </tr>
    <tr>
        <td bgcolor="#1f6798" style="width: 2%;">&nbsp;</td>
        <td style="padding: 20px 0; background-color: #ffffff;">
            <table align="center" border="0" cellpadding="0" cellspacing="0" width="100%">
                <tr>
                    <td style="text-align: center; padding-bottom: 30px;">
                        <img src="{logo}" width="200" alt="{app_name}">
                    </td>
                </tr>
                <tr>
                    <td style="padding: 0 40px;">
                        {content}
                    </td>
                </tr>
                <tr>
                    <td style="padding: 40px; font-size: 14px; border-top: 1px solid #f1f5f9; line-height: 1.5;">
                        <p style="margin: 0;">Thanks & Regards!</p>
                        <p style="margin: 4px 0; font-weight: bold;">Dr. Harish Mallapura Maheshwarappa</p>
                        <p style="margin: 0; font-size: 13px; color: #64748b;">
                            Faculty & Course Director<br/>
                            MBBS, MD, DNB, IDCCM, DM (Critical Care Medicine TMH, Mumbai), EDICM, MBA<br/>
                            Intensive Care Physician
                        </p>
                    </td>
                </tr>
            </table>
        </td>
        <td bgcolor="#1f6798" style="width: 2%;">&nbsp;</td>
    </tr>
    <tr bgcolor="#1f6798">
        <td colspan="3" width="100%" style="padding: 8px;">&nbsp;</td>
    </tr>
</table>
</body>
</html>
    """.strip()


def resolve_registration_thank_you_slug(subscription: str | None, package_name: str | None) -> str:
    """Relative path under email_template/ without .php (e.g. batch_15/thank_you, thank_you)."""
    sub = (subscription or "").strip()
    pkg = (package_name or "").strip()
    if sub == "Batch 3":
        if pkg == "Option 1":
            return "batch_3/thank_you_p1"
        if pkg == "Option 2":
            return "batch_3/thank_you_p2"
        return "thank_you"
    return _SUBSCRIPTION_TO_SLUG.get(sub, "thank_you")


def _decrypt_password_for_email(user: User) -> str:
    raw = (user.password or "").strip()
    if not raw:
        return ""
    try:
        return my_simple_crypt(raw, "decrypt")
    except Exception:
        logger.warning("could not decrypt password for thank-you email user_id=%s", user.id)
        return ""


def stored_password_for_email(user: User) -> str:
    """users.password column value (legacy encrypted ciphertext) for login emails."""
    return (user.password or "").strip()


def plaintext_password_for_password_mail(user: User) -> str:
    """Decrypted password — admin UI only when ADMIN_EXPOSE_PLAINTEXT_PASSWORD is enabled."""
    return _decrypt_password_for_email(user)


_PASSWORD_DECRYPT_PHP = re.compile(
    r"<\?=\s*my_simple_crypt\s*\(\s*\$user(?:_data)?->password\s*,\s*['\"]decrypt['\"]\s*\)\s*;?\s*\?>",
    re.IGNORECASE,
)
_PASSWORD_FIELD_PHP = re.compile(r"<\?=\s*\$user(?:_data)?->password\s*\?>", re.IGNORECASE)
_PASSWORD_PHP_ORPHAN = re.compile(r"password\s*,\s*['\"]decrypt['\"]\s*\)\s*\?>", re.IGNORECASE)


def _substitute_password_in_template(html: str, user: User) -> str:
    """Replace PHP password echoes with the stored encrypted password (not decrypted plaintext)."""
    pwd_esc = escape(stored_password_for_email(user))
    html = _PASSWORD_DECRYPT_PHP.sub(pwd_esc, html)
    html = _PASSWORD_FIELD_PHP.sub(pwd_esc, html)
    html = _PASSWORD_PHP_ORPHAN.sub(pwd_esc, html)
    return html


def _strip_payment_status_branch(html: str) -> str:
    """Keep only the Credit branch of email_template/thank_you.php-style conditionals."""
    html = re.sub(
        r"<\?php\s*if\s*\(\s*\$payment_data\s*\[\s*'payment_status'\s*\]\s*==\s*'Credit'\s*\)\s*\{\s*\?>",
        "",
        html,
        flags=re.IGNORECASE,
    )
    html = re.sub(
        r"<\?php\s*\}\s*else\s*\{\s*\?>.*?<\?php\s*\}\s*\?>",
        "",
        html,
        flags=re.DOTALL | re.IGNORECASE,
    )
    return html


def _substitute_php_echoes(html: str, user: User) -> str:
    settings = get_settings()
    app_name = escape(settings.email_app_name)
    asset_base = (settings.email_asset_base_url or "").rstrip("/")
    full_name = escape(f"{(user.title or '').strip()} {(user.name or '').strip()}".strip() or "Learner")
    email_esc = escape((user.email or "").strip())
    subscription_esc = escape((user.subscription or "").strip())

    # Core site variables
    html = html.replace("<?=APP_NAME?>", app_name)
    html = html.replace("<?=resources_url()?>", f"{asset_base}/")
    html = html.replace("<?=base_url('register')?>", f"{asset_base}/registration")
    html = html.replace("<?=base_url('login')?>", f"{asset_base}/login")
    
    # User object variants (PHP often uses $user or $user_data interchangeably in views)
    for pfx in ["$user_data", "$user"]:
        html = html.replace(f"<?={pfx}->email?>", email_esc)
        html = html.replace(f"<?={pfx}->subscription?>", subscription_esc)
        # Handle concatenated name variants
        html = html.replace(f"<?={pfx}->title.' '.$user_data->name?>", full_name)
        html = html.replace(f"<?={pfx}->title.' '.$user->name?>", full_name)
        html = re.sub(
            rf"<\?=\s*\{re.escape(pfx)}->title\s*\.\s*'\s*'\s*\.\s*({re.escape('$user_data')}|{re.escape('$user')})->name\s*\?>",
            full_name,
            html,
        )

    html = _substitute_password_in_template(html, user)
    return _fix_email_logo_src(html)


def _load_php_thank_you(slug: str) -> str | None:
    root = Path(get_settings().email_template_php_root)
    path = root / f"{slug}.php"
    if not path.is_file():
        return None
    return path.read_text(encoding="utf-8", errors="replace")


def _generic_credit_thank_you_inner(user: User) -> str:
    """Fallback when PHP file is missing: matches email_template/thank_you.php Credit branch."""
    settings = get_settings()
    name = escape(f"{(user.title or '').strip()} {(user.name or '').strip()}".strip() or "Learner")
    team = escape(settings.email_app_name)
    return f"""<p>Dear {name},</p>
    <p>Thank you for your registration. We are excited to have you in our classes.</p>
    <p>Warm Regards,<br/>
        Team {team}</p>"""


def render_registration_thank_you_html(user: User, package: Package | None) -> str:
    """
    Same template selection as PHP Register.php after successful payment (Credit).
    Loads legacy .php view when EMAIL_TEMPLATE_PHP_ROOT points at application/views/email_template.
    """
    pkg_name = (package.name if package else None) or None
    # Package.subscription matches PHP thank-you templates (CP 7, Batch 15, etc.).
    sub_for_slug = (package.subscription if package else None) or user.subscription
    slug = resolve_registration_thank_you_slug(sub_for_slug, pkg_name)
    raw = _load_php_thank_you(slug)
    if raw is None:
        logger.warning("thank-you template missing: %s.php — using generic body", slug)
        inner = _generic_credit_thank_you_inner(user)
    else:
        raw = _strip_payment_status_branch(raw)
        inner = _substitute_php_echoes(raw, user)
    if inner.lstrip().lower().startswith("<!doctype") or inner.lstrip().lower().startswith("<html"):
        return _fix_email_logo_src(inner)
    return _legacy_php_layout(inner)


def registration_success_template(
    title: str = "",
    name: str = "Learner",
    subscription: str = "Batch 15",
    package_name: str | None = None,
) -> str:
    """Used by scripts/test_email_sending.py; mirrors a successful registration thank-you."""
    u = User()
    u.title = title
    u.name = name
    u.email = "test@example.com"
    u.password = ""
    u.subscription = subscription
    pkg = Package(name=package_name, subscription=subscription) if package_name else None
    return render_registration_thank_you_html(u, pkg)


def paynow_template(name: str, subscription: str) -> str:
    raw = _load_php_thank_you("paynow")
    if raw:
        u = User(name=name, subscription=subscription)
        return _substitute_php_echoes(raw, u)
        
    return _legacy_php_layout(f"""
      <h2 style="color: #1f6798;">Payment Pending</h2>
      <p>Dear {escape(name)},</p>
      <p>Your registration for <strong>{escape(subscription)}</strong> is pending payment.</p>
      <p>Please complete your payment to activate your access.</p>
      <p style="margin-top: 20px;">
        <a href="{get_settings().email_asset_base_url}" style="display: inline-block; padding: 10px 20px; background-color: #1f6798; color: #ffffff; text-decoration: none; border-radius: 4px; font-weight: bold;">Complete Payment</a>
      </p>
    """)


PASSWORD_MAIL_SUBJECT = "Login Details - harishcriticalcareclasses.com"


def password_template_for_user(user: User) -> str:
    """Login-details email — password line shows users.password (encrypted), matching legacy PHP storage."""
    for slug in ["send_user_password", "send_password"]:
        raw = _load_php_thank_you(slug)
        if raw:
            return _substitute_php_echoes(raw, user)

    name = escape(f"{(user.title or '').strip()} {(user.name or '').strip()}".strip() or "Learner")
    email_esc = escape((user.email or "").strip())
    pwd_esc = escape(stored_password_for_email(user))
    return _legacy_php_layout(f"""
      <h2 style="color: #1f6798;">Your Login Details</h2>
      <p>Dear {name},</p>
      <p>Your account has been activated. You can now login to access your classes.</p>
      <p>Email: <strong>{email_esc}</strong></p>
      <p>Password: <strong>{pwd_esc}</strong></p>
      <p style="margin-top: 20px;">
        <a href="{get_settings().email_asset_base_url}/login" style="display: inline-block; padding: 10px 20px; background-color: #1f6798; color: #ffffff; text-decoration: none; border-radius: 4px; font-weight: bold;">Login Now</a>
      </p>
    """)


def password_template(name: str, email: str, password: str) -> str:
    """Backward-compatible wrapper; prefer password_template_for_user with a real User row."""
    u = User(name=name, email=email, password=password)
    return password_template_for_user(u)


def custom_template(subject: str, body_html: str) -> str:
    raw = _load_php_thank_you("send_custom_mail")
    if raw:
        # Note: Legacy send_custom_mail.php is often hardcoded. 
        # If it doesn't contain placeholders, we might be sending stale info.
        # We check for placeholders; if missing, we use our layout.
        if "<?=$message?>" in raw or "<?=$subject?>" in raw:
            html = raw.replace("<?=APP_NAME?>", escape(get_settings().email_app_name))
            html = html.replace("<?=resources_url()?>", f"{get_settings().email_asset_base_url}/")
            html = html.replace("<?=$subject?>", escape(subject))
            html = html.replace("<?=$message?>", body_html)
            return html

    return _legacy_php_layout(f"""
      <h2 style="color: #1f6798;">{escape(subject)}</h2>
      <div style="margin-top: 16px;">
        {body_html}
      </div>
    """)


def document_status_template(name: str, subscription: str, status: str) -> str:
    status_label = "Approved" if status == "1" else "Denied" if status == "2" else "Pending"
    status_color = "#10b981" if status == "1" else "#ef4444" if status == "2" else "#64748b"
    
    return _legacy_php_layout(f"""
      <h2 style="color: #1f6798;">Document Verification Update</h2>
      <p>Dear {escape(name)},</p>
      <p>Your document status for <strong>{escape(subscription)}</strong> has been updated:</p>
      <p style="font-size: 18px; font-weight: bold; color: {status_color}; margin: 15px 0;">{status_label}</p>
      {f'<p>You can now proceed to use the platform.</p>' if status == "1" else '<p>Please re-upload valid documents from your profile.</p>'}
      <p style="margin-top: 20px;">
        <a href="{get_settings().email_asset_base_url}/dashboard" style="display: inline-block; padding: 10px 20px; background-color: #1f6798; color: #ffffff; text-decoration: none; border-radius: 4px; font-weight: bold;">Go to Dashboard</a>
      </p>
    """)


def _render_db_template(raw_html: str, values: dict[str, str]) -> str:
    rendered = raw_html
    for key, value in values.items():
        rendered = rendered.replace(f"{{{{{key}}}}}", value)
    return rendered


def _looks_like_html(text: str) -> bool:
    return bool(re.search(r"<[a-zA-Z][^>]*>", text))


def _plain_text_to_email_html(text: str) -> str:
    """Allow admins to write plain text while still sending valid HTML emails."""
    cleaned = (text or "").replace("\r\n", "\n").strip()
    if not cleaned:
        return ""
    paragraphs = [p.strip() for p in cleaned.split("\n\n") if p.strip()]
    if not paragraphs:
        return f"<p>{escape(cleaned).replace(chr(10), '<br/>')}</p>"
    return "".join(f"<p>{escape(p).replace(chr(10), '<br/>')}</p>" for p in paragraphs)


def _batch_for_subscription(db: Session, subscription: str, package: Package | None = None) -> BatchMaster | None:
    sub = (subscription or "").strip()
    if not sub and package and (package.subscription or "").strip():
        sub = (package.subscription or "").strip()
    if not sub:
        return None
    return (
        db.query(BatchMaster)
        .filter(BatchMaster.name.ilike(sub))
        .order_by(BatchMaster.id.desc())
        .first()
    )


def resolve_batch_template_email(
    db: Session,
    user: User,
    template_type: str,
    *,
    default_subject: str,
    default_html: str,
    status_label: str = "",
    package: Package | None = None,
) -> tuple[str, str]:
    """
    Resolve custom batch template and render placeholders.
    Falls back to provided subject/body when custom template is missing or invalid.
    """
    batch = _batch_for_subscription(db, user.subscription or "", package)
    if not batch:
        return default_subject, default_html

    row = (
        db.query(EmailTemplateMaster)
        .filter(
            EmailTemplateMaster.batch_id == batch.id,
            EmailTemplateMaster.template_type == (template_type or "").strip().lower(),
            EmailTemplateMaster.status == "1",
        )
        .order_by(EmailTemplateMaster.id.desc())
        .first()
    )
    if not row:
        return default_subject, default_html

    settings = get_settings()
    subject = (row.subject or "").strip() or default_subject
    raw_html = (row.body_html or "").strip()
    if not raw_html:
        return subject, default_html

    full_name = " ".join([p for p in [user.title or "", user.name or ""] if (p or "").strip()]).strip() or "Learner"
    safe_values = {
        "name": escape(full_name),
        "email": escape((user.email or "").strip()),
        "subscription": escape((user.subscription or "").strip()),
        "batch_name": escape((batch.name or "").strip()),
        "dashboard_url": escape(f"{settings.email_asset_base_url}/dashboard"),
        "login_url": escape(f"{settings.email_asset_base_url}/login"),
        "status_label": escape(status_label),
    }
    rendered_html = _render_db_template(raw_html, safe_values)
    if not _looks_like_html(rendered_html):
        rendered_html = _legacy_php_layout(_plain_text_to_email_html(rendered_html))
    return subject, _fix_email_logo_src(rendered_html)


def password_reset_otp_template(name: str, otp: str, ttl_minutes: int) -> str:
    safe_name = escape((name or "Learner").strip() or "Learner")
    safe_otp = escape(otp.strip())
    ttl = max(1, int(ttl_minutes))
    content = f"""
        <p style="font-family: 'Quicksand', sans-serif; font-size: 15px;">Hello {safe_name},</p>
        <p style="font-family: 'Quicksand', sans-serif; font-size: 15px;">
            Use this verification code to reset your Harish Critical Care Classes password.
            It expires in <strong>{ttl} minutes</strong>.
        </p>
        <p style="text-align: center; margin: 32px 0;">
            <span style="display: inline-block; font-size: 28px; font-weight: 700; letter-spacing: 0.35em;
                color: #1f6798; font-family: 'Quicksand', monospace; padding: 16px 28px;
                background: #f0f7fc; border-radius: 6px; border: 1px solid #cfe4f3;">
                {safe_otp}
            </span>
        </p>
        <p style="font-family: 'Quicksand', sans-serif; font-size: 14px; color: #64748b;">
            If you did not request this, you can ignore this email. Your password will not change
            unless you enter this code on the forgot-password page.
        </p>
    """
    return _legacy_php_layout(content)


def event_registration_confirmation_template(*, registration_number: str) -> str:
    safe_reg = escape((registration_number or "").strip())
    content = f"""
        <p style="font-family: 'Quicksand', sans-serif; font-size: 15px;">Dear Delegate,</p>
        <p style="font-family: 'Quicksand', sans-serif; font-size: 15px;">
            Thank you for registering for the 1st National ICU-ID Conclave 2026.
        </p>
        <p style="font-family: 'Quicksand', sans-serif; font-size: 15px;">
            We are happy to welcome you to the conference and look forward to your participation in this
            academic event focused on Intensive Care Medicine and Infectious Diseases.
        </p>
        <p style="font-family: 'Quicksand', sans-serif; font-size: 15px; margin: 24px 0;">
            Your registration number — <strong style="font-size: 18px; color: #1f6798;">{safe_reg}</strong>
        </p>
        <p style="font-family: 'Quicksand', sans-serif; font-size: 15px; margin-top: 28px;">
            Warm regards,<br/><br/>
            <strong>Dr. Harish Mallapura Maheshwarappa</strong><br/>
            Organizing Chairman<br/>
            ICU-ID Conclave 2026
        </p>
    """
    return _legacy_php_layout(content)


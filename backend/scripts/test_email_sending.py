import sys
import os
from pathlib import Path

# Add the app directory to sys.path to allow importing from 'app'
sys.path.append(str(Path(__file__).resolve().parent.parent))

from app.services.mailer import send_html_email
from app.services.email_templates import registration_success_template
from app.core.config import get_settings

def test_smtp():
    settings = get_settings()
    print(f"Testing SMTP with Host: {settings.smtp_host}:{settings.smtp_port}")
    print(f"From: {settings.smtp_from}")
    print(f"CC: {settings.smtp_cc}")
    print(f"BCC: {settings.smtp_bcc}")
    
    test_email = os.getenv("TEST_EMAIL_TO", "test@example.com").strip()
    subject = "SMTP Test - Online Master Classes"
    html = registration_success_template(title="Dr.", name="Test User", subscription="Batch 15")
    
    try:
        print(f"Attempting to send test email to {test_email}...")
        send_html_email(
            to_email=test_email,
            subject=subject,
            html=html,
            cc=settings.smtp_cc,
            bcc=settings.smtp_bcc
        )
        print("Success! Email sent through SMTP2GO.")
    except Exception as e:
        print(f"FAILED: {e}")

if __name__ == "__main__":
    test_smtp()

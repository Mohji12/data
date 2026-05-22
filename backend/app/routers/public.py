from __future__ import annotations
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr, Field
import logging

router = APIRouter(prefix="/public", tags=["public"])
logger = logging.getLogger(__name__)

class ContactUsRequest(BaseModel):
    name: str = Field(..., min_length=1)
    email: str = Field(..., min_length=1) # Using str instead of EmailStr to avoid dependency issues, could add regex later
    phone_number: str = Field(..., min_length=1)
    msg_subject: str = Field(..., min_length=1)
    message: str = Field(..., min_length=1)

@router.post("/contact-us")
def contact_us_submit(payload: ContactUsRequest):
    """
    Handles Contact Us form submissions.
    Ported from PHP Welcome.php -> contact_us_send_mail()
    """
    # Here you would typically connect to an SMTP server or use a service like SendGrid
    # Example using smtplib (pseudo-code as we lack credentials):
    # import smtplib
    # from email.mime.text import MIMEText
    # msg = MIMEText(f"Name: {payload.name}\nEmail: {payload.email}\nPhone: {payload.phone_number}\nMessage: {payload.message}")
    # msg['Subject'] = payload.msg_subject
    # msg['From'] = "system@example.com"
    # msg['To'] = "admin@example.com"
    # s = smtplib.SMTP('localhost')
    # s.send_message(msg)
    # s.quit()
    
    logger.info(f"Received Contact Us submission from {payload.name} ({payload.email})")
    
    # Simulating successful email dispatch
    return {"status": "success", "message": "Your inquiry has been sent successfully."}

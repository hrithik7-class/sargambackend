"""
Email service for sending verification OTPs via SMTP.
"""
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from src.config import settings


def send_verification_email(to_email: str, otp: str) -> None:
    """
    Send OTP verification email to the user.

    Args:
        to_email: Recipient email address
        otp: 6-digit OTP code

    Raises:
        ValueError: If SMTP is not configured
        smtplib.SMTPException: On send failure
    """
    if not settings.SMTP_USER or not settings.SMTP_PASSWORD:
        raise ValueError("SMTP is not configured. Set SMTP_USER and SMTP_PASSWORD in .env")

    subject = "Verify your SargamAI account"
    html_body = f"""
    <html>
    <body style="font-family: sans-serif; line-height: 1.6; color: #333;">
        <h2>Verify your email</h2>
        <p>Thanks for signing up for SargamAI!</p>
        <p>Your verification code is:</p>
        <p style="font-size: 24px; font-weight: bold; letter-spacing: 4px; color: #0891b2;">{otp}</p>
        <p>This code expires in 10 minutes.</p>
        <p>If you didn't create an account, you can ignore this email.</p>
        <hr style="border: none; border-top: 1px solid #eee; margin: 20px 0;">
        <p style="color: #666; font-size: 12px;">SargamAI - AI-Powered Music Lyrics Generator</p>
    </body>
    </html>
    """
    text_body = f"""Verify your SargamAI account

Your verification code is: {otp}

This code expires in 10 minutes.

If you didn't create an account, you can ignore this email.

---
SargamAI - AI-Powered Music Lyrics Generator
"""

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = settings.SMTP_FROM
    msg["To"] = to_email
    msg.attach(MIMEText(text_body, "plain"))
    msg.attach(MIMEText(html_body, "html"))

    with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
        server.starttls()
        server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
        server.sendmail(settings.SMTP_FROM, to_email, msg.as_string())

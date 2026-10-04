from email.message import EmailMessage
from app.core.config import settings
import smtplib



def send_voicemail_notifications(to_email: str, caller_number: str):
    msg = EmailMessage()
    msg["Subject"] = "Новое голосовое сообщение"
    msg["From"] = settings.EMAIL_HOST_USER
    msg["To"] = to_email
    msg.set_content(f"Сообщение от {caller_number}")

    with smtplib.SMTP(host="smtp.gmail.com",port=587) as server:
        server.starttls()
        server.login(user=settings.EMAIL_HOST_USER, password=settings.EMAIL_HOST_PASSWORD)
        server.send_message(msg)



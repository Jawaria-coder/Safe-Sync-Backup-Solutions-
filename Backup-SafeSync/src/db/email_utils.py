EMAIL_ADDRESS = "safesync4@gmail.com"
EMAIL_PASSWORD = "ymyb hmtp mqxc urwg"

import smtplib
from email.message import EmailMessage

def send_plain_email(to_email, subject, body):
    try:
        msg = EmailMessage()
        msg["From"] = EMAIL_ADDRESS
        msg["To"] = to_email
        msg["Subject"] = subject
        msg.set_content(body)

        # Connect to Gmail’s SMTP server
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()  # Secure the connection
            server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
            server.send_message(msg)

        print(f"[INFO] Email sent successfully to {to_email}")

    except Exception as e:
        print(f"[ERROR] Failed to send email to {to_email}: {e}")
        raise e

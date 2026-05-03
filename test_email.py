import os
import sys
import smtplib
import ssl
from email.message import EmailMessage


host = os.getenv("SMTP_HOST", "smtp-relay.gmail.com")
port = int(os.getenv("SMTP_PORT", "587"))
user = os.getenv("SMTP_USER") or "hui.fu@ieee.org" # e.g., sender@ieee.org (Google Workspace)
pwd = os.getenv("SMTP_PASS")  # App Password for the account
sender = os.getenv("SMTP_SENDER", user or "")
to_addr = os.getenv("SMTP_TO", user or "")

if not user or not pwd:
    print("Missing SMTP_USER or SMTP_PASS. For Google Workspace, use an App Password (2‑Step Verification required).")
    sys.exit(1)

msg = EmailMessage()
msg["Subject"] = "Gmail SMTP Test"
msg["From"] = sender
msg["To"] = to_addr or user
msg.set_content("This is a test via Gmail SMTP (Google Workspace).")

context = ssl.create_default_context()

try:
    with smtplib.SMTP(host, port) as s:
        s.ehlo()
        s.starttls(context=context)
        s.ehlo()
        s.login(user, pwd)
        s.send_message(msg)
    print("Sent via Gmail SMTP")
except smtplib.SMTPAuthenticationError as e:
    code, resp = e.args
    print(f"Auth failed ({code}): {resp}")
    print(
        "Tips: 1) Ensure 2‑Step Verification is enabled and use an App Password; "
        "2) If using SMTP Relay, switch host to smtp-relay.gmail.com and configure allowed IP/auth in Admin Console; "
        "3) Verify SPF/DKIM for your domain (ieee.org) for better deliverability."
    )
    sys.exit(1)
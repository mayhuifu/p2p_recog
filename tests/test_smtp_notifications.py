import unittest
from unittest.mock import patch

from recognition_portal import create_app
from recognition_portal.notifications import delivered_messages, send_email


class SmtpNotificationTests(unittest.TestCase):
    def test_send_email_uses_smtp_when_configured(self) -> None:
        app = create_app(
            {
                "TESTING": True,
                "SECRET_KEY": "test",
                "DATABASE_URL": "sqlite://",
                "SMTP_HOST": "smtp.example.com",
                "SMTP_PORT": 587,
                "SMTP_USERNAME": "mailer",
                "SMTP_PASSWORD": "secret",
                "SMTP_FROM_EMAIL": "noreply@example.com",
                "SMTP_USE_TLS": True,
                "SMTP_USE_SSL": False,
                "SMTP_TIMEOUT_SECONDS": 15,
            }
        )

        with patch("recognition_portal.notifications.smtplib.SMTP") as smtp_class:
            smtp = smtp_class.return_value.__enter__.return_value

            send_email(
                app,
                event_type="magic_link",
                recipient_email="ada@example.com",
                subject="Your sign-in link",
                body="Hello from SMTP",
            )

        smtp_class.assert_called_once_with("smtp.example.com", 587, timeout=15)
        smtp.starttls.assert_called_once_with()
        smtp.login.assert_called_once_with("mailer", "secret")
        smtp.send_message.assert_called_once()
        message = smtp.send_message.call_args.args[0]
        self.assertEqual(message["From"], "noreply@example.com")
        self.assertEqual(message["To"], "ada@example.com")
        self.assertEqual(message["Subject"], "Your sign-in link")
        self.assertEqual(delivered_messages(app)[-1]["recipient_email"], "ada@example.com")

    def test_send_email_skips_smtp_when_not_configured(self) -> None:
        app = create_app(
            {
                "TESTING": True,
                "SECRET_KEY": "test",
                "DATABASE_URL": "sqlite://",
            }
        )

        with patch("recognition_portal.notifications.smtplib.SMTP") as smtp_class:
            send_email(
                app,
                event_type="magic_link",
                recipient_email="ada@example.com",
                subject="Your sign-in link",
                body="Fallback path",
            )

        smtp_class.assert_not_called()
        self.assertEqual(delivered_messages(app)[-1]["recipient_email"], "ada@example.com")


if __name__ == "__main__":
    unittest.main()

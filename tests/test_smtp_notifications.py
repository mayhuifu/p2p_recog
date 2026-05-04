import unittest
from unittest.mock import MagicMock, patch

import app as app_entrypoint
from recognition_portal import create_app
from recognition_portal.notifications import (
    delivered_messages,
    send_email,
    send_smtp_test_email,
    verify_smtp_connection,
)


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

    def test_verify_smtp_connection_uses_smtp_when_configured(self) -> None:
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
            verify_smtp_connection(app)

        smtp_class.assert_called_once_with("smtp.example.com", 587, timeout=15)
        smtp.starttls.assert_called_once_with()
        smtp.login.assert_called_once_with("mailer", "secret")
        smtp.send_message.assert_not_called()

    def test_verify_smtp_connection_requires_config(self) -> None:
        app = create_app(
            {
                "TESTING": True,
                "SECRET_KEY": "test",
                "DATABASE_URL": "sqlite://",
            }
        )

        with self.assertRaisesRegex(RuntimeError, "SMTP is not configured"):
            verify_smtp_connection(app)

    def test_send_smtp_test_email_sends_expected_message(self) -> None:
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
            send_smtp_test_email(app, "ada@example.com")

        smtp.send_message.assert_called_once()
        message = smtp.send_message.call_args.args[0]
        self.assertEqual(message["From"], "noreply@example.com")
        self.assertEqual(message["To"], "ada@example.com")
        self.assertEqual(message["Subject"], "P2P Recognition SMTP test")
        self.assertIn("P2P Recognition Portal SMTP check", message.get_content())


class AppCliTests(unittest.TestCase):
    def test_main_smtp_test_verifies_and_exits(self) -> None:
        fake_app = MagicMock()

        with patch("app.create_app", return_value=fake_app), patch(
            "app.verify_smtp_connection"
        ) as verify_mock, patch("app.send_smtp_test_email") as send_mock, patch(
            "builtins.print"
        ) as print_mock, patch(
            "sys.argv", ["app.py", "--smtp-test"]
        ):
            app_entrypoint.main()

        verify_mock.assert_called_once_with(fake_app)
        send_mock.assert_not_called()
        fake_app.run.assert_not_called()
        print_mock.assert_called_once_with("SMTP connection and login succeeded.")

    def test_main_smtp_test_to_sends_and_exits(self) -> None:
        fake_app = MagicMock()

        with patch("app.create_app", return_value=fake_app), patch(
            "app.verify_smtp_connection"
        ) as verify_mock, patch("app.send_smtp_test_email") as send_mock, patch(
            "builtins.print"
        ) as print_mock, patch(
            "sys.argv", ["app.py", "--smtp-test-to", "ada@example.com"]
        ):
            app_entrypoint.main()

        verify_mock.assert_not_called()
        send_mock.assert_called_once_with(fake_app, "ada@example.com")
        fake_app.run.assert_not_called()
        print_mock.assert_called_once_with("SMTP test email sent to ada@example.com.")


if __name__ == "__main__":
    unittest.main()

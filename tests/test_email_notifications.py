import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import app as app_entrypoint
from recognition_portal import create_app
from recognition_portal.notifications import (
    _build_outlook_plugin_prompt,
    delivered_messages,
    send_email,
    send_email_test_message,
    verify_email_delivery_configuration,
)


class EmailNotificationTests(unittest.TestCase):
    def test_send_email_uses_outlook_plugin_backend_when_configured(self) -> None:
        app = create_app(
            {
                "TESTING": True,
                "SECRET_KEY": "test",
                "DATABASE_URL": "sqlite://",
                "EMAIL_DELIVERY_BACKEND": "outlook_plugin",
                "CODEX_BIN": "codex",
                "OUTLOOK_PLUGIN_TIMEOUT_SECONDS": 45,
                "OUTLOOK_PLUGIN_WORKDIR": "/tmp",
            }
        )

        with tempfile.NamedTemporaryFile("w+", encoding="utf-8", delete=False) as output_file:
            output_path = output_file.name

        expected_prompt = _build_outlook_plugin_prompt(
            {
                "event_type": "magic_link",
                "recipient_email": "ada@example.com",
                "subject": "Your sign-in link",
                "body": "Hello from Outlook",
            }
        )

        def fake_run(*args, **kwargs):
            Path(output_path).write_text("SENT", encoding="utf-8")
            self.assertEqual(
                args[0],
                [
                    "/usr/local/bin/codex",
                    "exec",
                    "--skip-git-repo-check",
                    "--sandbox",
                    "read-only",
                    "--cd",
                    str(Path("/tmp").resolve()),
                    "--output-last-message",
                    output_path,
                    expected_prompt,
                ],
            )
            self.assertEqual(kwargs["capture_output"], True)
            self.assertEqual(kwargs["text"], True)
            self.assertEqual(kwargs["timeout"], 45)
            self.assertEqual(kwargs["check"], False)
            return MagicMock(returncode=0, stdout="", stderr="")

        with patch("recognition_portal.notifications.shutil.which", return_value="/usr/local/bin/codex"), patch(
            "recognition_portal.notifications.tempfile.NamedTemporaryFile"
        ) as temp_file_factory, patch(
            "recognition_portal.notifications.subprocess.run",
            side_effect=fake_run,
        ):
            temp_file_factory.return_value.__enter__.return_value.name = output_path
            send_email(
                app,
                event_type="magic_link",
                recipient_email="ada@example.com",
                subject="Your sign-in link",
                body="Hello from Outlook",
            )

        self.assertEqual(delivered_messages(app)[-1]["recipient_email"], "ada@example.com")
        Path(output_path).unlink(missing_ok=True)

    def test_send_email_skips_real_delivery_when_backend_is_local(self) -> None:
        app = create_app(
            {
                "TESTING": True,
                "SECRET_KEY": "test",
                "DATABASE_URL": "sqlite://",
                "EMAIL_DELIVERY_BACKEND": "local",
            }
        )

        with patch("recognition_portal.notifications.subprocess.run") as run_mock:
            send_email(
                app,
                event_type="magic_link",
                recipient_email="ada@example.com",
                subject="Your sign-in link",
                body="Local-only path",
            )

        run_mock.assert_not_called()
        self.assertEqual(delivered_messages(app)[-1]["recipient_email"], "ada@example.com")

    def test_verify_email_delivery_configuration_requires_backend(self) -> None:
        app = create_app(
            {
                "TESTING": True,
                "SECRET_KEY": "test",
                "DATABASE_URL": "sqlite://",
                "EMAIL_DELIVERY_BACKEND": "local",
            }
        )

        with self.assertRaisesRegex(RuntimeError, "Email delivery is not configured"):
            verify_email_delivery_configuration(app)

    def test_verify_email_delivery_configuration_checks_codex_binary(self) -> None:
        app = create_app(
            {
                "TESTING": True,
                "SECRET_KEY": "test",
                "DATABASE_URL": "sqlite://",
                "EMAIL_DELIVERY_BACKEND": "outlook_plugin",
                "CODEX_BIN": "codex",
            }
        )

        with patch("recognition_portal.notifications.shutil.which", return_value="/usr/local/bin/codex"):
            verify_email_delivery_configuration(app)

    def test_send_email_test_message_uses_expected_subject(self) -> None:
        app = create_app(
            {
                "TESTING": True,
                "SECRET_KEY": "test",
                "DATABASE_URL": "sqlite://",
                "EMAIL_DELIVERY_BACKEND": "outlook_plugin",
                "CODEX_BIN": "codex",
            }
        )

        with patch("recognition_portal.notifications.verify_email_delivery_configuration"), patch(
            "recognition_portal.notifications._deliver_email"
        ) as deliver_mock:
            send_email_test_message(app, "ada@example.com")

        payload = deliver_mock.call_args.args[1]
        self.assertEqual(payload["recipient_email"], "ada@example.com")
        self.assertEqual(payload["subject"], "P2P Recognition email delivery test")
        self.assertIn("P2P Recognition Portal delivery check", payload["body"])


class AppCliTests(unittest.TestCase):
    def test_main_email_backend_check_verifies_and_exits(self) -> None:
        fake_app = MagicMock()

        with patch("app.create_app", return_value=fake_app), patch(
            "app.verify_email_delivery_configuration"
        ) as verify_mock, patch("app.send_email_test_message") as send_mock, patch(
            "builtins.print"
        ) as print_mock, patch(
            "sys.argv", ["app.py", "--email-backend-check"]
        ):
            app_entrypoint.main()

        verify_mock.assert_called_once_with(fake_app)
        send_mock.assert_not_called()
        fake_app.run.assert_not_called()
        print_mock.assert_called_once_with("Email delivery backend configuration looks valid.")

    def test_main_email_test_to_sends_and_exits(self) -> None:
        fake_app = MagicMock()

        with patch("app.create_app", return_value=fake_app), patch(
            "app.verify_email_delivery_configuration"
        ) as verify_mock, patch("app.send_email_test_message") as send_mock, patch(
            "builtins.print"
        ) as print_mock, patch(
            "sys.argv", ["app.py", "--email-test-to", "ada@example.com"]
        ):
            app_entrypoint.main()

        verify_mock.assert_not_called()
        send_mock.assert_called_once_with(fake_app, "ada@example.com")
        fake_app.run.assert_not_called()
        print_mock.assert_called_once_with("Email test message sent to ada@example.com.")


if __name__ == "__main__":
    unittest.main()

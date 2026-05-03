import re
import tempfile
import unittest

from recognition_portal import create_app
from recognition_portal.db import session_scope
from recognition_portal.employee_directory import import_employees_from_csv
from recognition_portal.models import LoginToken
from recognition_portal.notifications import delivered_messages


class MagicLinkAuthTests(unittest.TestCase):
    def setUp(self) -> None:
        self.app = create_app(
            {
                "TESTING": True,
                "SECRET_KEY": "test",
                "DATABASE_URL": "sqlite://",
                "ALLOWED_LOGIN_DOMAINS": ["example.com"],
                "PUBLIC_BASE_URL": "http://testserver",
            }
        )
        self.client = self.app.test_client()

    def _seed_directory(self) -> None:
        csv_text = "\n".join(
            [
                "name,email,role,department,region,active,manager_email",
                "Ada Lovelace,ada@example.com,admin,Operations,US,yes,",
                "Grace Hopper,grace@example.com,manager,Engineering,US,no,ada@example.com",
            ]
        )
        with self.app.app_context():
            with session_scope(self.app) as session:
                import_employees_from_csv(session, csv_text)

    def _extract_token(self) -> str:
        message = delivered_messages(self.app)[-1]
        match = re.search(r"/login/consume\?token=([^\s]+)", message["body"])
        self.assertIsNotNone(match)
        return match.group(1)

    def test_login_request_creates_token_and_delivers_email(self) -> None:
        response = self.client.post("/login", data={"email": "ada@example.com"}, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Check your email for a magic sign-in link.", response.data)
        self.assertEqual(delivered_messages(self.app)[-1]["recipient_email"], "ada@example.com")

        with self.app.app_context():
            with session_scope(self.app) as session:
                tokens = session.query(LoginToken).all()
                self.assertEqual(len(tokens), 1)
                self.assertEqual(tokens[0].status, "pending")

    def test_login_request_persists_token_and_notification_on_file_backed_sqlite(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            app = create_app(
                {
                    "TESTING": True,
                    "SECRET_KEY": "test",
                    "DATABASE_URL": f"sqlite:///{temp_dir}/portal.db",
                    "ALLOWED_LOGIN_DOMAINS": ["example.com"],
                    "PUBLIC_BASE_URL": "http://testserver",
                }
            )
            client = app.test_client()

            response = client.post("/login", data={"email": "ada@example.com"}, follow_redirects=True)

            self.assertEqual(response.status_code, 200)
            self.assertIn(b"Check your email for a magic sign-in link.", response.data)
            self.assertEqual(delivered_messages(app)[-1]["recipient_email"], "ada@example.com")

            with app.app_context():
                with session_scope(app) as session:
                    tokens = session.query(LoginToken).all()
                    self.assertEqual(len(tokens), 1)
                    self.assertEqual(tokens[0].status, "pending")

    def test_active_employee_can_consume_token_and_access_admin_route(self) -> None:
        self._seed_directory()
        self.client.post("/login", data={"email": "ada@example.com"})
        token = self._extract_token()

        response = self.client.get(f"/login/consume?token={token}", follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Recognize a coworker", response.data)
        self.assertIn(b"admin", response.data)

        response = self.client.get("/admin/employees")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Employee directory", response.data)

    def test_inactive_employee_is_signed_in_but_blocked(self) -> None:
        self._seed_directory()
        self.client.post("/login", data={"email": "grace@example.com"})
        token = self._extract_token()

        response = self.client.get(f"/login/consume?token={token}", follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Signed in, but inactive", response.data)

        response = self.client.get("/admin/employees", follow_redirects=True)
        self.assertIn(b"not active for portal actions yet", response.data)

    def test_unknown_company_email_is_signed_in_pending_directory(self) -> None:
        self.client.post("/login", data={"email": "newhire@example.com"})
        token = self._extract_token()

        response = self.client.get(f"/login/consume?token={token}", follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"pending directory approval", response.data)

    def test_non_company_domain_is_rejected(self) -> None:
        response = self.client.post("/login", data={"email": "guest@gmail.com"}, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"approved company email domain", response.data)


if __name__ == "__main__":
    unittest.main()

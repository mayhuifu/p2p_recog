import unittest

from recognition_portal import create_app
from recognition_portal.auth import build_session_user
from recognition_portal.db import session_scope
from recognition_portal.employee_directory import import_employees_from_csv


class TextOnlyMessageFieldTests(unittest.TestCase):
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
        self._seed_directory()

    def _seed_directory(self) -> None:
        csv_text = "\n".join(
            [
                "name,email,role,department,region,active,manager_email",
                "Ada Lovelace,ada@example.com,admin,Operations,US,yes,",
                "Grace Hopper,grace@example.com,manager,Engineering,US,yes,ada@example.com",
                "Alan Turing,alan@example.com,employee,Engineering,EU,yes,grace@example.com",
                "Barbara Liskov,barbara@example.com,manager,Product,US,yes,ada@example.com",
                "Katherine Johnson,katherine@example.com,employee,Engineering,US,yes,barbara@example.com",
            ]
        )
        with self.app.app_context():
            with session_scope(self.app) as session:
                import_employees_from_csv(session, csv_text)

    def _login_as(self, email: str) -> None:
        with self.app.app_context():
            with session_scope(self.app) as session_db:
                session_user = build_session_user(session_db, email)
        with self.client.session_transaction() as client_session:
            client_session["user_session"] = {
                "email": session_user.email,
                "role": session_user.role,
                "access_state": session_user.access_state,
                "employee_id": session_user.employee_id,
                "display_name": session_user.display_name,
            }

    def test_portal_uses_textareas_and_no_file_upload_inputs(self) -> None:
        self._login_as("alan@example.com")

        response = self.client.get("/portal")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data.count(b'<textarea name="message"'), 2)
        self.assertNotIn(b'type="file"', response.data)
        self.assertNotIn(b'enctype="multipart/form-data"', response.data)

    def test_points_edit_uses_textarea_and_no_file_upload_inputs(self) -> None:
        self._login_as("alan@example.com")
        self.client.post(
            "/recognitions/points",
            data={
                "recipient_ids": ["5"],
                "category": "Innovation",
                "company_value": "",
                "points": "10",
                "message": "Katherine documented the edge case clearly and made the next handoff much calmer.",
            },
            follow_redirects=True,
        )

        response = self.client.get("/recognitions/points/1/edit")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b'<textarea name="message"', response.data)
        self.assertNotIn(b'type="file"', response.data)
        self.assertNotIn(b'enctype="multipart/form-data"', response.data)

    def test_non_monetary_message_renders_as_escaped_text(self) -> None:
        self._login_as("alan@example.com")

        response = self.client.post(
            "/recognitions/non-monetary",
            data={
                "recipient_id": "5",
                "category": "Teamwork",
                "company_value": "",
                "message": "<b>Bold thanks</b> for jumping in quickly and closing the last release gaps cleanly.",
            },
            follow_redirects=True,
        )

        self.assertIn(b"Recognition published to the company feed.", response.data)
        self.assertIn(b"&lt;b&gt;Bold thanks&lt;/b&gt;", response.data)
        self.assertNotIn(b"<b>Bold thanks</b>", response.data)

    def test_points_message_renders_as_escaped_text_in_pending_summary(self) -> None:
        self._login_as("alan@example.com")

        response = self.client.post(
            "/recognitions/points",
            data={
                "recipient_ids": ["5"],
                "category": "Ownership",
                "company_value": "",
                "points": "25",
                "message": "<i>Plain text only</i> should remain text in the pending request summary for the sender.",
            },
            follow_redirects=True,
        )

        self.assertIn(b"Points recognition submitted for manager approval.", response.data)
        self.assertIn(b"&lt;i&gt;Plain text only&lt;/i&gt;", response.data)
        self.assertNotIn(b"<i>Plain text only</i>", response.data)


if __name__ == "__main__":
    unittest.main()

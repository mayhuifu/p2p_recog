import unittest
import tempfile

from recognition_portal import create_app
from recognition_portal.auth import build_session_user
from recognition_portal.db import session_scope
from recognition_portal.employee_directory import import_employees_from_csv
from recognition_portal.models import Recognition
from recognition_portal.notifications import delivered_messages


class NonMonetaryRecognitionTests(unittest.TestCase):
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

    def test_active_employee_can_publish_non_monetary_recognition(self) -> None:
        self._login_as("alan@example.com")
        response = self.client.post(
            "/recognitions/non-monetary",
            data={
                "recipient_id": "5",
                "category": "Teamwork",
                "company_value": "Trust",
                "message": "Katherine stepped in fast and unblocked the release with excellent pairing help.",
            },
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Recognition published to the company feed.", response.data)
        self.assertIn(b"Katherine Johnson", response.data)

        with self.app.app_context():
            with session_scope(self.app) as session:
                recognitions = session.query(Recognition).all()
                self.assertEqual(len(recognitions), 1)
                self.assertEqual(recognitions[0].recognition_type, "non_monetary")
                self.assertEqual(recognitions[0].category, "Teamwork")

        messages = delivered_messages(self.app)
        self.assertEqual(len(messages), 2)
        self.assertEqual(messages[0]["recipient_email"], "katherine@example.com")
        self.assertEqual(messages[1]["recipient_email"], "barbara@example.com")

    def test_non_monetary_recognition_persists_notifications_on_file_backed_sqlite(self) -> None:
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
            with app.app_context():
                with session_scope(app) as session:
                    import_employees_from_csv(session, csv_text)
                    session_user = build_session_user(session, "alan@example.com")
            with client.session_transaction() as client_session:
                client_session["user_session"] = {
                    "email": session_user.email,
                    "role": session_user.role,
                    "access_state": session_user.access_state,
                    "employee_id": session_user.employee_id,
                    "display_name": session_user.display_name,
                }

            response = client.post(
                "/recognitions/non-monetary",
                data={
                    "recipient_id": "5",
                    "category": "Teamwork",
                    "company_value": "Trust",
                    "message": "Katherine stepped in fast and unblocked the release with excellent pairing help.",
                },
                follow_redirects=True,
            )

            self.assertEqual(response.status_code, 200)
            self.assertIn(b"Recognition published to the company feed.", response.data)
            self.assertEqual(len(delivered_messages(app)), 2)

    def test_self_recognition_is_blocked(self) -> None:
        self._login_as("alan@example.com")
        response = self.client.post(
            "/recognitions/non-monetary",
            data={
                "recipient_id": "3",
                "category": "Teamwork",
                "company_value": "",
                "message": "I would like to thank myself for doing my own work today.",
            },
            follow_redirects=True,
        )
        self.assertIn(b"You cannot recognize yourself.", response.data)

    def test_duplicate_recognition_is_blocked_for_fourteen_days(self) -> None:
        self._login_as("alan@example.com")
        payload = {
            "recipient_id": "5",
            "category": "Ownership",
            "company_value": "",
            "message": "Katherine took ownership of the customer bug and stayed with it until everything was resolved.",
        }
        self.client.post("/recognitions/non-monetary", data=payload, follow_redirects=True)
        response = self.client.post("/recognitions/non-monetary", data=payload, follow_redirects=True)
        self.assertIn(b"already recognized this coworker", response.data)

    def test_portal_feed_shows_recent_published_recognitions(self) -> None:
        self._login_as("alan@example.com")
        self.client.post(
            "/recognitions/non-monetary",
            data={
                "recipient_id": "5",
                "category": "Customer Impact",
                "company_value": "Customer Care",
                "message": "Katherine handled the support escalation with calm follow-through and clear updates.",
            },
            follow_redirects=True,
        )
        response = self.client.get("/portal")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Recent recognitions", response.data)
        self.assertIn(b"Customer Impact", response.data)

    def test_sender_manager_can_hide_recognition_and_sender_gets_notified(self) -> None:
        self._login_as("alan@example.com")
        self.client.post(
            "/recognitions/non-monetary",
            data={
                "recipient_id": "5",
                "category": "Teamwork",
                "company_value": "",
                "message": "Katherine jumped into incident response and helped team recover quickly.",
            },
            follow_redirects=True,
        )

        self._login_as("grace@example.com")
        response = self.client.post(
            "/recognitions/1/moderate",
            data={"action_type": "hidden", "reason": "Manager review requested while content is checked."},
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Recognition hidden.", response.data)
        self.assertNotIn(b"Katherine jumped into incident response", response.data)

        messages = delivered_messages(self.app)
        self.assertEqual(messages[-1]["recipient_email"], "alan@example.com")
        self.assertIn("hidden", messages[-1]["subject"])

    def test_recipient_manager_can_remove_recognition(self) -> None:
        self._login_as("alan@example.com")
        self.client.post(
            "/recognitions/non-monetary",
            data={
                "recipient_id": "5",
                "category": "Ownership",
                "company_value": "",
                "message": "Katherine owned tricky product handoff and kept stakeholders aligned all week long.",
            },
            follow_redirects=True,
        )

        self._login_as("barbara@example.com")
        response = self.client.post(
            "/recognitions/1/moderate",
            data={"action_type": "removed", "reason": "Post removed after recipient-side escalation."},
            follow_redirects=True,
        )
        self.assertIn(b"Recognition removed.", response.data)

    def test_unauthorized_employee_cannot_moderate(self) -> None:
        self._login_as("alan@example.com")
        self.client.post(
            "/recognitions/non-monetary",
            data={
                "recipient_id": "5",
                "category": "Innovation",
                "company_value": "",
                "message": "Katherine found clever path through difficult edge case and documented it clearly.",
            },
            follow_redirects=True,
        )

        self._login_as("katherine@example.com")
        response = self.client.post(
            "/recognitions/1/moderate",
            data={"action_type": "hidden", "reason": "Trying unauthorized moderation."},
            follow_redirects=True,
        )
        self.assertIn(b"do not have permission", response.data)

    def test_admin_review_queue_shows_moderated_recognition(self) -> None:
        self._login_as("alan@example.com")
        self.client.post(
            "/recognitions/non-monetary",
            data={
                "recipient_id": "5",
                "category": "Above and Beyond",
                "company_value": "",
                "message": "Katherine stayed late, tied off open work, and kept customers updated without dropping details.",
            },
            follow_redirects=True,
        )
        self._login_as("grace@example.com")
        self.client.post(
            "/recognitions/1/moderate",
            data={"action_type": "hidden", "reason": "Temporary review hold."},
            follow_redirects=True,
        )

        self._login_as("ada@example.com")
        response = self.client.get("/portal")
        self.assertIn(b"Recognition review queue", response.data)
        self.assertIn(b"hidden", response.data)


if __name__ == "__main__":
    unittest.main()

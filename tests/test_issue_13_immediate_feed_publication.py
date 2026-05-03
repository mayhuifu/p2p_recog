import unittest

from sqlalchemy import select

from recognition_portal import create_app
from recognition_portal.auth import build_session_user
from recognition_portal.db import session_scope
from recognition_portal.employee_directory import import_employees_from_csv
from recognition_portal.models import PointsRecognitionRequest, Recognition


class ImmediateFeedPublicationTests(unittest.TestCase):
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

    def test_non_monetary_recognition_is_published_immediately_and_visible_after_redirect(self) -> None:
        self._login_as("alan@example.com")
        message = "Katherine jumped in quickly, resolved the last blockers, and kept the release handoff calm."

        response = self.client.post(
            "/recognitions/non-monetary",
            data={
                "recipient_id": "5",
                "category": "Teamwork",
                "company_value": "Trust",
                "message": message,
            },
            follow_redirects=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Recognition published to the company feed.", response.data)
        self.assertIn(message.encode("utf-8"), response.data)
        self.assertIn(b"Recent recognitions", response.data)

        with self.app.app_context():
            with session_scope(self.app) as session:
                recognition = session.scalar(select(Recognition))

        self.assertIsNotNone(recognition)
        self.assertEqual(recognition.status, "published")
        self.assertEqual(recognition.recognition_type, "non_monetary")
        self.assertIsNotNone(recognition.published_at)

    def test_points_request_does_not_appear_in_company_feed_before_approval(self) -> None:
        self._login_as("alan@example.com")
        points_message = (
            "Katherine handled the customer follow-through carefully and kept the final launch handoff organized."
        )

        response = self.client.post(
            "/recognitions/points",
            data={
                "recipient_ids": ["5"],
                "category": "Ownership",
                "company_value": "",
                "points": "25",
                "message": points_message,
            },
            follow_redirects=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Points recognition submitted for manager approval.", response.data)
        self.assertIn(b"Recent recognitions", response.data)
        self.assertIn(b"No recognition posts yet.", response.data)
        self.assertIn(b"Pending points requests", response.data)

        with self.app.app_context():
            with session_scope(self.app) as session:
                recognition_count = session.scalar(select(Recognition.id).limit(1))
                points_request = session.scalar(select(PointsRecognitionRequest))

        self.assertIsNone(recognition_count)
        self.assertIsNotNone(points_request)
        self.assertEqual(points_request.status, "pending_approval")


if __name__ == "__main__":
    unittest.main()

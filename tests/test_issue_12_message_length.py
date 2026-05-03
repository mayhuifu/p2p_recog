import unittest

from sqlalchemy import select

from recognition_portal import create_app
from recognition_portal.auth import build_session_user
from recognition_portal.db import session_scope
from recognition_portal.employee_directory import import_employees_from_csv
from recognition_portal.models import PointsRecognitionRequest, Recognition


class MessageLengthRuleTests(unittest.TestCase):
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

    def test_non_monetary_recognition_rejects_message_shorter_than_20_characters(self) -> None:
        self._login_as("alan@example.com")

        response = self.client.post(
            "/recognitions/non-monetary",
            data={
                "recipient_id": "5",
                "category": "Teamwork",
                "company_value": "",
                "message": "Too short message",
            },
            follow_redirects=True,
        )

        self.assertIn(b"Recognition message must be at least 20 characters.", response.data)

        with self.app.app_context():
            with session_scope(self.app) as session:
                recognitions = session.scalars(select(Recognition)).all()
        self.assertEqual(recognitions, [])

    def test_non_monetary_recognition_rejects_message_longer_than_500_characters(self) -> None:
        self._login_as("alan@example.com")

        response = self.client.post(
            "/recognitions/non-monetary",
            data={
                "recipient_id": "5",
                "category": "Teamwork",
                "company_value": "",
                "message": "a" * 501,
            },
            follow_redirects=True,
        )

        self.assertIn(b"Recognition message must be 500 characters or fewer.", response.data)

    def test_non_monetary_recognition_accepts_trimmed_message_at_boundary_length(self) -> None:
        self._login_as("alan@example.com")
        message = f"  {'a' * 20}  "

        response = self.client.post(
            "/recognitions/non-monetary",
            data={
                "recipient_id": "5",
                "category": "Teamwork",
                "company_value": "",
                "message": message,
            },
            follow_redirects=True,
        )

        self.assertIn(b"Recognition published to the company feed.", response.data)

        with self.app.app_context():
            with session_scope(self.app) as session:
                recognition = session.scalar(select(Recognition))
        self.assertEqual(recognition.message, "a" * 20)

    def test_points_request_rejects_message_outside_length_bounds(self) -> None:
        self._login_as("alan@example.com")

        short_response = self.client.post(
            "/recognitions/points",
            data={
                "recipient_ids": ["5"],
                "category": "Ownership",
                "company_value": "",
                "points": "10",
                "message": "short points note",
            },
            follow_redirects=True,
        )
        self.assertIn(b"Recognition message must be at least 20 characters.", short_response.data)

        long_response = self.client.post(
            "/recognitions/points",
            data={
                "recipient_ids": ["5"],
                "category": "Ownership",
                "company_value": "",
                "points": "10",
                "message": "b" * 501,
            },
            follow_redirects=True,
        )
        self.assertIn(b"Recognition message must be 500 characters or fewer.", long_response.data)

        with self.app.app_context():
            with session_scope(self.app) as session:
                requests = session.scalars(select(PointsRecognitionRequest)).all()
        self.assertEqual(requests, [])

    def test_points_edit_rejects_invalid_message_length_and_preserves_existing_request(self) -> None:
        self._login_as("alan@example.com")
        original_message = "Katherine kept the handoff calm and documented every remaining blocker clearly."
        self.client.post(
            "/recognitions/points",
            data={
                "recipient_ids": ["5"],
                "category": "Innovation",
                "company_value": "",
                "points": "25",
                "message": original_message,
            },
            follow_redirects=True,
        )

        response = self.client.post(
            "/recognitions/points/1/edit",
            data={
                "recipient_ids": ["5"],
                "category": "Innovation",
                "company_value": "",
                "points": "25",
                "message": "short edit message",
            },
            follow_redirects=True,
        )

        self.assertIn(b"Recognition message must be at least 20 characters.", response.data)

        with self.app.app_context():
            with session_scope(self.app) as session:
                request_record = session.get(PointsRecognitionRequest, 1)
        self.assertEqual(request_record.message, original_message)


if __name__ == "__main__":
    unittest.main()

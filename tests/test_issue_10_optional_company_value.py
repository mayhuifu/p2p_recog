import unittest

from sqlalchemy import select

from recognition_portal import create_app
from recognition_portal.auth import build_session_user
from recognition_portal.db import session_scope
from recognition_portal.employee_directory import import_employees_from_csv
from recognition_portal.models import PointsRecognitionRequest, Recognition


class OptionalCompanyValueTests(unittest.TestCase):
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

    def test_non_monetary_recognition_allows_blank_company_value(self) -> None:
        self._login_as("alan@example.com")

        response = self.client.post(
            "/recognitions/non-monetary",
            data={
                "recipient_id": "5",
                "category": "Teamwork",
                "company_value": "",
                "message": "Katherine stepped into the handoff quickly and kept the release checklist moving.",
            },
            follow_redirects=True,
        )

        self.assertIn(b"Recognition published to the company feed.", response.data)

        with self.app.app_context():
            with session_scope(self.app) as session:
                recognition = session.scalar(select(Recognition))

        self.assertIsNotNone(recognition)
        self.assertIsNone(recognition.company_value)

    def test_non_monetary_recognition_rejects_invalid_company_value(self) -> None:
        self._login_as("alan@example.com")

        response = self.client.post(
            "/recognitions/non-monetary",
            data={
                "recipient_id": "5",
                "category": "Teamwork",
                "company_value": "Integrity",
                "message": "Katherine stepped into the handoff quickly and kept the release checklist moving.",
            },
            follow_redirects=True,
        )

        self.assertIn(b"Choose a valid company value.", response.data)

    def test_points_request_allows_blank_company_value(self) -> None:
        self._login_as("alan@example.com")

        response = self.client.post(
            "/recognitions/points",
            data={
                "recipient_ids": ["5"],
                "category": "Ownership",
                "company_value": "",
                "points": "25",
                "message": "Katherine handled the customer follow-through carefully and removed confusion from the handoff.",
            },
            follow_redirects=True,
        )

        self.assertIn(b"Points recognition submitted for manager approval.", response.data)

        with self.app.app_context():
            with session_scope(self.app) as session:
                request_record = session.scalar(select(PointsRecognitionRequest))

        self.assertIsNotNone(request_record)
        self.assertIsNone(request_record.company_value)

    def test_points_request_rejects_invalid_company_value(self) -> None:
        self._login_as("alan@example.com")

        response = self.client.post(
            "/recognitions/points",
            data={
                "recipient_ids": ["5"],
                "category": "Ownership",
                "company_value": "Integrity",
                "points": "25",
                "message": "Katherine handled the customer follow-through carefully and removed confusion from the handoff.",
            },
            follow_redirects=True,
        )

        self.assertIn(b"Choose a valid company value.", response.data)

    def test_points_edit_can_add_or_remove_optional_company_value(self) -> None:
        self._login_as("alan@example.com")
        self.client.post(
            "/recognitions/points",
            data={
                "recipient_ids": ["5"],
                "category": "Innovation",
                "company_value": "",
                "points": "10",
                "message": "Katherine found a calmer path through the edge case and documented it for the team.",
            },
            follow_redirects=True,
        )

        add_value_response = self.client.post(
            "/recognitions/points/1/edit",
            data={
                "recipient_ids": ["5"],
                "category": "Innovation",
                "company_value": "Craft",
                "points": "10",
                "message": "Katherine found a calmer path through the edge case and documented it for the team.",
            },
            follow_redirects=True,
        )
        self.assertIn(b"Pending points recognition updated.", add_value_response.data)

        with self.app.app_context():
            with session_scope(self.app) as session:
                request_record = session.get(PointsRecognitionRequest, 1)
                self.assertEqual(request_record.company_value, "Craft")

        remove_value_response = self.client.post(
            "/recognitions/points/1/edit",
            data={
                "recipient_ids": ["5"],
                "category": "Innovation",
                "company_value": "",
                "points": "10",
                "message": "Katherine found a calmer path through the edge case and documented it for the team.",
            },
            follow_redirects=True,
        )
        self.assertIn(b"Pending points recognition updated.", remove_value_response.data)

        with self.app.app_context():
            with session_scope(self.app) as session:
                request_record = session.get(PointsRecognitionRequest, 1)
                self.assertIsNone(request_record.company_value)


if __name__ == "__main__":
    unittest.main()

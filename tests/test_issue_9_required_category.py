import unittest

from sqlalchemy import select

from recognition_portal import create_app
from recognition_portal.auth import build_session_user
from recognition_portal.db import session_scope
from recognition_portal.employee_directory import import_employees_from_csv
from recognition_portal.models import PointsRecognitionRecipient, PointsRecognitionRequest, Recognition


class RequiredCategoryTests(unittest.TestCase):
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

    def test_non_monetary_recognition_requires_category(self) -> None:
        self._login_as("alan@example.com")

        response = self.client.post(
            "/recognitions/non-monetary",
            data={
                "recipient_id": "5",
                "category": "",
                "company_value": "",
                "message": "Katherine stepped in quickly and helped close the final release blockers cleanly.",
            },
            follow_redirects=True,
        )

        self.assertIn(b"Choose a valid recognition category.", response.data)

        with self.app.app_context():
            with session_scope(self.app) as session:
                recognitions = session.scalars(select(Recognition)).all()

        self.assertEqual(recognitions, [])

    def test_points_recognition_requires_category(self) -> None:
        self._login_as("alan@example.com")

        response = self.client.post(
            "/recognitions/points",
            data={
                "recipient_ids": ["5"],
                "category": "",
                "company_value": "",
                "points": "25",
                "message": "Katherine kept the customer handoff steady and covered the last mile without confusion.",
            },
            follow_redirects=True,
        )

        self.assertIn(b"Choose a valid recognition category.", response.data)

        with self.app.app_context():
            with session_scope(self.app) as session:
                requests = session.scalars(select(PointsRecognitionRequest)).all()

        self.assertEqual(requests, [])

    def test_points_edit_requires_category_and_preserves_existing_request(self) -> None:
        self._login_as("alan@example.com")
        self.client.post(
            "/recognitions/points",
            data={
                "recipient_ids": ["5"],
                "category": "Ownership",
                "company_value": "",
                "points": "10",
                "message": "Katherine drove the follow-through on a tricky operational handoff and kept everyone aligned.",
            },
            follow_redirects=True,
        )

        response = self.client.post(
            "/recognitions/points/1/edit",
            data={
                "recipient_ids": ["5"],
                "category": "",
                "company_value": "",
                "points": "25",
                "message": "Dropping the category on edit should be rejected and the old request should stay intact.",
            },
            follow_redirects=True,
        )

        self.assertIn(b"Choose a valid recognition category.", response.data)

        with self.app.app_context():
            with session_scope(self.app) as session:
                request_record = session.get(PointsRecognitionRequest, 1)
                recipients = session.scalars(
                    select(PointsRecognitionRecipient).where(
                        PointsRecognitionRecipient.request_id == request_record.id
                    )
                ).all()

        self.assertEqual(request_record.category, "Ownership")
        self.assertEqual(request_record.requested_points_per_recipient, 10)
        self.assertEqual([recipient.recipient_id for recipient in recipients], [5])


if __name__ == "__main__":
    unittest.main()

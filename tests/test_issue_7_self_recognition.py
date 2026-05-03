import unittest

from sqlalchemy import select

from recognition_portal import create_app
from recognition_portal.auth import build_session_user
from recognition_portal.db import session_scope
from recognition_portal.employee_directory import import_employees_from_csv
from recognition_portal.models import PointsRecognitionRequest, PointsRecognitionRecipient


class SelfRecognitionGuardrailTests(unittest.TestCase):
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

    def test_portal_recipient_choosers_do_not_offer_current_user(self) -> None:
        self._login_as("alan@example.com")

        response = self.client.get("/portal")

        self.assertEqual(response.status_code, 200)
        self.assertNotIn(b'<option value="3"', response.data)
        self.assertIn(b'<option value="5"', response.data)

    def test_non_monetary_self_recognition_is_rejected(self) -> None:
        self._login_as("alan@example.com")

        response = self.client.post(
            "/recognitions/non-monetary",
            data={
                "recipient_id": "3",
                "category": "Teamwork",
                "company_value": "",
                "message": "I should not be able to submit recognition for my own work here.",
            },
            follow_redirects=True,
        )

        self.assertIn(b"You cannot recognize yourself.", response.data)

    def test_points_self_recognition_is_rejected(self) -> None:
        self._login_as("alan@example.com")

        response = self.client.post(
            "/recognitions/points",
            data={
                "recipient_ids": ["3"],
                "category": "Ownership",
                "company_value": "",
                "points": "25",
                "message": "I should not be able to request points recognition for myself either.",
            },
            follow_redirects=True,
        )

        self.assertIn(b"You cannot recognize yourself with points.", response.data)

    def test_points_edit_cannot_be_changed_to_self_recognition(self) -> None:
        self._login_as("alan@example.com")
        self.client.post(
            "/recognitions/points",
            data={
                "recipient_ids": ["5"],
                "category": "Innovation",
                "company_value": "",
                "points": "10",
                "message": "Katherine documented the edge case clearly and made the handoff much smoother.",
            },
            follow_redirects=True,
        )

        response = self.client.post(
            "/recognitions/points/1/edit",
            data={
                "recipient_ids": ["3"],
                "category": "Innovation",
                "company_value": "",
                "points": "10",
                "message": "Trying to mutate a valid request into self-recognition should be blocked cleanly.",
            },
            follow_redirects=True,
        )

        self.assertIn(b"You cannot recognize yourself with points.", response.data)

        with self.app.app_context():
            with session_scope(self.app) as session:
                request_record = session.scalar(select(PointsRecognitionRequest))
                recipients = session.scalars(
                    select(PointsRecognitionRecipient).where(
                        PointsRecognitionRecipient.request_id == request_record.id
                    )
                ).all()

        self.assertEqual(request_record.requested_points_per_recipient, 10)
        self.assertEqual([recipient.recipient_id for recipient in recipients], [5])


if __name__ == "__main__":
    unittest.main()

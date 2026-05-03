import unittest
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from recognition_portal import create_app
from recognition_portal.auth import build_session_user
from recognition_portal.db import session_scope
from recognition_portal.employee_directory import import_employees_from_csv
from recognition_portal.models import PointsRecognitionRecipient, PointsRecognitionRequest, Recognition


class DuplicateRecognitionGuardrailTests(unittest.TestCase):
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

    def _age_non_monetary_recognition(self, recognition_id: int, *, days_old: int) -> None:
        aged_at = datetime.now(timezone.utc) - timedelta(days=days_old)
        with self.app.app_context():
            with session_scope(self.app) as session:
                recognition = session.get(Recognition, recognition_id)
                recognition.created_at = aged_at
                recognition.published_at = aged_at

    def _age_points_request(self, request_id: int, *, days_old: int) -> None:
        aged_at = datetime.now(timezone.utc) - timedelta(days=days_old)
        with self.app.app_context():
            with session_scope(self.app) as session:
                request_record = session.get(PointsRecognitionRequest, request_id)
                request_record.created_at = aged_at
                request_record.updated_at = aged_at

    def test_points_request_is_blocked_after_recent_non_monetary_recognition(self) -> None:
        self._login_as("alan@example.com")
        self.client.post(
            "/recognitions/non-monetary",
            data={
                "recipient_id": "5",
                "category": "Teamwork",
                "company_value": "",
                "message": "Katherine unblocked a messy release handoff and kept the team coordinated.",
            },
            follow_redirects=True,
        )

        response = self.client.post(
            "/recognitions/points",
            data={
                "recipient_ids": ["5"],
                "category": "Ownership",
                "company_value": "",
                "points": "25",
                "message": "Trying to send a second recognition too soon should be blocked for the same coworker.",
            },
            follow_redirects=True,
        )

        self.assertIn(b"already recognized one or more selected coworkers", response.data)

        with self.app.app_context():
            with session_scope(self.app) as session:
                requests = session.scalars(select(PointsRecognitionRequest)).all()

        self.assertEqual(requests, [])

    def test_non_monetary_recognition_is_blocked_after_recent_points_request(self) -> None:
        self._login_as("alan@example.com")
        self.client.post(
            "/recognitions/points",
            data={
                "recipient_ids": ["5"],
                "category": "Ownership",
                "company_value": "",
                "points": "10",
                "message": "Katherine handled a tough customer handoff and kept all of the details aligned.",
            },
            follow_redirects=True,
        )

        response = self.client.post(
            "/recognitions/non-monetary",
            data={
                "recipient_id": "5",
                "category": "Teamwork",
                "company_value": "",
                "message": "A second recognition right away should still be blocked across recognition types.",
            },
            follow_redirects=True,
        )

        self.assertIn(b"You already recognized this coworker in the last 14 days.", response.data)

    def test_duplicate_points_request_is_allowed_after_cooldown_expires(self) -> None:
        self._login_as("alan@example.com")
        first_response = self.client.post(
            "/recognitions/points",
            data={
                "recipient_ids": ["5"],
                "category": "Customer Impact",
                "company_value": "",
                "points": "10",
                "message": "Katherine took ownership of the escalation and kept the customer communication stable.",
            },
            follow_redirects=True,
        )
        self.assertIn(b"Points recognition submitted for manager approval.", first_response.data)

        self._age_points_request(1, days_old=15)

        second_response = self.client.post(
            "/recognitions/points",
            data={
                "recipient_ids": ["5"],
                "category": "Customer Impact",
                "company_value": "",
                "points": "25",
                "message": "After the cooldown, another recognition for the same coworker should be allowed again.",
            },
            follow_redirects=True,
        )

        self.assertIn(b"Points recognition submitted for manager approval.", second_response.data)

        with self.app.app_context():
            with session_scope(self.app) as session:
                requests = session.scalars(select(PointsRecognitionRequest)).all()

        self.assertEqual(len(requests), 2)

    def test_non_monetary_duplicate_is_allowed_after_cooldown_expires(self) -> None:
        self._login_as("alan@example.com")
        first_response = self.client.post(
            "/recognitions/non-monetary",
            data={
                "recipient_id": "5",
                "category": "Innovation",
                "company_value": "",
                "message": "Katherine found a clean path through the edge case and documented it well for the team.",
            },
            follow_redirects=True,
        )
        self.assertIn(b"Recognition published to the company feed.", first_response.data)

        self._age_non_monetary_recognition(1, days_old=15)

        second_response = self.client.post(
            "/recognitions/non-monetary",
            data={
                "recipient_id": "5",
                "category": "Innovation",
                "company_value": "",
                "message": "The cooldown should expire so a later recognition can be published without being blocked.",
            },
            follow_redirects=True,
        )

        self.assertIn(b"Recognition published to the company feed.", second_response.data)

    def test_points_edit_cannot_add_recently_recognized_recipient_from_another_request(self) -> None:
        self._login_as("alan@example.com")
        self.client.post(
            "/recognitions/points",
            data={
                "recipient_ids": ["2"],
                "category": "Teamwork",
                "company_value": "",
                "points": "10",
                "message": "Grace stepped into a difficult planning session and helped unblock the rest of the group.",
            },
            follow_redirects=True,
        )
        self.client.post(
            "/recognitions/points",
            data={
                "recipient_ids": ["5"],
                "category": "Ownership",
                "company_value": "",
                "points": "10",
                "message": "Katherine carried the operational follow-through and kept the launch checklist tight.",
            },
            follow_redirects=True,
        )

        response = self.client.post(
            "/recognitions/points/2/edit",
            data={
                "recipient_ids": ["2", "5"],
                "category": "Ownership",
                "company_value": "",
                "points": "10",
                "message": "Editing a request cannot be used to add a coworker who is still inside the duplicate window.",
            },
            follow_redirects=True,
        )

        self.assertIn(b"already recognized one or more selected coworkers", response.data)

        with self.app.app_context():
            with session_scope(self.app) as session:
                second_request = session.get(PointsRecognitionRequest, 2)
                recipients = session.scalars(
                    select(PointsRecognitionRecipient).where(
                        PointsRecognitionRecipient.request_id == second_request.id
                    )
                ).all()

        self.assertEqual([recipient.recipient_id for recipient in recipients], [5])


if __name__ == "__main__":
    unittest.main()

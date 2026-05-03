import unittest

from sqlalchemy import select

from recognition_portal import create_app
from recognition_portal.auth import build_session_user
from recognition_portal.db import session_scope
from recognition_portal.employee_directory import import_employees_from_csv
from recognition_portal.models import PointsRecognitionRequest, PointsRecognitionRecipient
from recognition_portal.notifications import delivered_messages


class PointsRecognitionRequestTests(unittest.TestCase):
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

    def test_active_employee_can_submit_pending_points_request_with_multiple_recipients(self) -> None:
        self._login_as("alan@example.com")
        response = self.client.post(
            "/recognitions/points",
            data={
                "recipient_ids": ["2", "5"],
                "category": "Teamwork",
                "company_value": "Trust",
                "points": "25",
                "message": "Grace and Katherine pushed through urgent launch blockers and kept execution calm.",
            },
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Points recognition submitted for manager approval.", response.data)
        self.assertIn(b"50 total points", response.data)

        with self.app.app_context():
            with session_scope(self.app) as session:
                request_record = session.scalar(select(PointsRecognitionRequest))
                self.assertIsNotNone(request_record)
                self.assertEqual(request_record.status, "pending_approval")
                self.assertEqual(request_record.requested_points_per_recipient, 25)
                self.assertEqual(request_record.total_requested_points, 50)
                recipients = session.scalars(
                    select(PointsRecognitionRecipient).where(
                        PointsRecognitionRecipient.request_id == request_record.id
                    )
                ).all()
                self.assertEqual(len(recipients), 2)

        self.assertEqual(delivered_messages(self.app), [])

    def test_points_request_requires_valid_preset(self) -> None:
        self._login_as("alan@example.com")
        response = self.client.post(
            "/recognitions/points",
            data={
                "recipient_ids": ["5"],
                "category": "Ownership",
                "company_value": "",
                "points": "15",
                "message": "Katherine carried ownership through difficult handoff and customer follow-up work.",
            },
            follow_redirects=True,
        )
        self.assertIn(b"Choose a valid points amount.", response.data)

    def test_sender_can_edit_pending_points_request(self) -> None:
        self._login_as("alan@example.com")
        self.client.post(
            "/recognitions/points",
            data={
                "recipient_ids": ["2", "5"],
                "category": "Innovation",
                "company_value": "",
                "points": "25",
                "message": "Grace and Katherine worked through a complex product edge case with strong teamwork.",
            },
            follow_redirects=True,
        )

        response = self.client.post(
            "/recognitions/points/1/edit",
            data={
                "recipient_ids": ["5"],
                "category": "Innovation",
                "company_value": "Craft",
                "points": "50",
                "message": "Katherine worked through a complex product edge case and documented the path clearly.",
            },
            follow_redirects=True,
        )
        self.assertIn(b"Pending points recognition updated.", response.data)
        self.assertIn(b"50 total points", response.data)

        with self.app.app_context():
            with session_scope(self.app) as session:
                request_record = session.scalar(select(PointsRecognitionRequest))
                self.assertEqual(request_record.requested_points_per_recipient, 50)
                self.assertEqual(request_record.total_requested_points, 50)
                recipients = session.scalars(
                    select(PointsRecognitionRecipient).where(
                        PointsRecognitionRecipient.request_id == request_record.id
                    )
                ).all()
                self.assertEqual([recipient.recipient_id for recipient in recipients], [5])

    def test_sender_can_cancel_pending_points_request(self) -> None:
        self._login_as("alan@example.com")
        self.client.post(
            "/recognitions/points",
            data={
                "recipient_ids": ["5"],
                "category": "Customer Impact",
                "company_value": "",
                "points": "10",
                "message": "Katherine handled the customer follow-up cleanly and prevented extra churn.",
            },
            follow_redirects=True,
        )

        response = self.client.post("/recognitions/points/1/cancel", follow_redirects=True)
        self.assertIn(b"Pending points recognition canceled.", response.data)
        self.assertIn(b"canceled", response.data)

        with self.app.app_context():
            with session_scope(self.app) as session:
                request_record = session.scalar(select(PointsRecognitionRequest))
                self.assertEqual(request_record.status, "canceled")

    def test_sender_can_delete_pending_points_request(self) -> None:
        self._login_as("alan@example.com")
        self.client.post(
            "/recognitions/points",
            data={
                "recipient_ids": ["5"],
                "category": "Above and Beyond",
                "company_value": "",
                "points": "10",
                "message": "Katherine stayed late to close small but critical gaps before the release cutoff.",
            },
            follow_redirects=True,
        )

        response = self.client.post("/recognitions/points/1/delete", follow_redirects=True)
        self.assertIn(b"Pending points recognition deleted.", response.data)

        with self.app.app_context():
            with session_scope(self.app) as session:
                requests = session.scalars(select(PointsRecognitionRequest)).all()
                self.assertEqual(requests, [])

    def test_portal_shows_pending_points_request_summary(self) -> None:
        self._login_as("alan@example.com")
        self.client.post(
            "/recognitions/points",
            data={
                "recipient_ids": ["2", "5"],
                "category": "Teamwork",
                "company_value": "",
                "points": "10",
                "message": "Grace and Katherine kept cross-team work aligned during an unusually noisy sprint.",
            },
            follow_redirects=True,
        )

        response = self.client.get("/portal")
        self.assertIn(b"Pending points requests", response.data)
        self.assertIn(b"2 recipients", response.data)
        self.assertIn(b"20 total points", response.data)


if __name__ == "__main__":
    unittest.main()

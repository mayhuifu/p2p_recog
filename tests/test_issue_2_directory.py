import io
import unittest

from recognition_portal import create_app
from recognition_portal.db import session_scope
from recognition_portal.employee_directory import import_employees_from_csv
from recognition_portal.models import Employee


class EmployeeDirectoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.app = create_app(
            {
                "TESTING": True,
                "SECRET_KEY": "test",
                "DATABASE_URL": "sqlite://",
            }
        )
        self.client = self.app.test_client()

    def test_csv_import_creates_and_links_manager_hierarchy(self) -> None:
        csv_text = "\n".join(
            [
                "name,email,role,department,region,active,manager_email",
                "Ada Lovelace,ada@example.com,admin,Operations,US,yes,",
                "Grace Hopper,grace@example.com,manager,Engineering,US,yes,ada@example.com",
                "Alan Turing,alan@example.com,employee,Engineering,EU,no,grace@example.com",
            ]
        )

        with self.app.app_context():
            with session_scope(self.app) as session:
                result = import_employees_from_csv(session, csv_text)

            with session_scope(self.app) as session:
                employees = {employee.email: employee for employee in session.query(Employee).all()}
                self.assertEqual(result.created, 3)
                self.assertEqual(result.updated, 0)
                self.assertEqual(employees["grace@example.com"].manager.email, "ada@example.com")
                self.assertEqual(employees["alan@example.com"].manager.email, "grace@example.com")
                self.assertFalse(employees["alan@example.com"].is_active)

    def test_directory_routes_render_and_import(self) -> None:
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Web app foundation in place", response.data)

        data = {
            "csv_text": "\n".join(
                [
                    "name,email,role,department,region,active,manager_email",
                    "Ada Lovelace,ada@example.com,admin,Operations,US,yes,",
                ]
            )
        }
        response = self.client.post("/admin/employees/import", data=data, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Ada Lovelace", response.data)
        self.assertIn(b"Active", response.data)

    def test_upload_csv_file_is_supported(self) -> None:
        csv_text = "name,email,role,department,region,active,manager_email\nAda Lovelace,ada@example.com,admin,Operations,US,yes,\n"
        response = self.client.post(
            "/admin/employees/import",
            data={"csv_file": (io.BytesIO(csv_text.encode("utf-8")), "employees.csv")},
            content_type="multipart/form-data",
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Ada Lovelace", response.data)


if __name__ == "__main__":
    unittest.main()

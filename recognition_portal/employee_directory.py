from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.orm import selectinload

from .models import Employee


class DirectoryImportError(ValueError):
    pass


@dataclass
class DirectoryImportResult:
    created: int
    updated: int
    total_rows: int


def _normalize_header_map(row: dict[str, str]) -> dict[str, str]:
    return {(key or "").strip().lower(): (value or "").strip() for key, value in row.items()}


def _normalize_email(value: str) -> str:
    email = value.strip().lower()
    if not email:
        raise DirectoryImportError("Email is required for every employee row.")
    return email


def _parse_active(value: str) -> bool:
    if value == "":
        return True
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "y", "active"}:
        return True
    if normalized in {"0", "false", "no", "n", "inactive"}:
        return False
    raise DirectoryImportError(f"Unsupported active value: {value!r}")


def list_employees(session: Session) -> list[Employee]:
    stmt = (
        select(Employee)
        .options(selectinload(Employee.manager))
        .order_by(Employee.name.asc(), Employee.email.asc())
    )
    return list(session.scalars(stmt))


def list_managers(session: Session) -> list[Employee]:
    return list(session.scalars(select(Employee).order_by(Employee.name.asc(), Employee.email.asc())))


def get_employee(session: Session, employee_id: int) -> Optional[Employee]:
    return session.get(Employee, employee_id)


def import_employees_from_csv(session: Session, csv_text: str) -> DirectoryImportResult:
    if not csv_text.strip():
        raise DirectoryImportError("Paste or upload a CSV file before importing.")

    reader = csv.DictReader(io.StringIO(csv_text))
    if not reader.fieldnames:
        raise DirectoryImportError("CSV input must include a header row.")

    seen_emails: set[str] = set()
    prepared_rows: list[dict[str, object]] = []
    for row_number, raw_row in enumerate(reader, start=2):
        row = _normalize_header_map(raw_row)
        name = row.get("name", "")
        email = _normalize_email(row.get("email", ""))
        if not name:
            raise DirectoryImportError(f"Row {row_number}: name is required.")
        if email in seen_emails:
            raise DirectoryImportError(f"Row {row_number}: duplicate email {email}.")
        seen_emails.add(email)

        prepared_rows.append(
            {
                "row_number": row_number,
                "name": name,
                "email": email,
                "role": row.get("role", "") or "employee",
                "department": row.get("department", "") or None,
                "region": row.get("region", "") or None,
                "is_active": _parse_active(row.get("active", "")),
                "manager_email": row.get("manager_email", "") or row.get("manager", "") or None,
            }
        )

    existing_by_email = {
        employee.email: employee
        for employee in session.scalars(select(Employee).where(Employee.email.in_([row["email"] for row in prepared_rows])))
    }

    created = 0
    updated = 0
    touched_by_email: dict[str, Employee] = {}
    for row in prepared_rows:
        employee = existing_by_email.get(row["email"])
        if employee is None:
            employee = Employee(email=row["email"], name=row["name"])
            session.add(employee)
            created += 1
        else:
            updated += 1

        employee.name = row["name"]
        employee.role = row["role"]
        employee.department = row["department"]
        employee.region = row["region"]
        employee.is_active = row["is_active"]
        touched_by_email[employee.email] = employee

    session.flush()

    all_import_emails = [row["email"] for row in prepared_rows]
    all_manager_emails = [
        manager_email.strip().lower()
        for manager_email in [row["manager_email"] for row in prepared_rows]
        if isinstance(manager_email, str) and manager_email.strip()
    ]
    looked_up_emails = sorted(set(all_import_emails + all_manager_emails))
    employees_by_email = {
        employee.email: employee
        for employee in session.scalars(select(Employee).where(Employee.email.in_(looked_up_emails)))
    }

    for row in prepared_rows:
        employee = employees_by_email[row["email"]]
        manager_email = row["manager_email"]
        if not manager_email:
            employee.manager = None
            continue

        manager_email = manager_email.strip().lower()
        if manager_email == employee.email:
            raise DirectoryImportError(f"Row {row['row_number']}: employee cannot manage themselves.")

        manager = employees_by_email.get(manager_email)
        if manager is None:
            raise DirectoryImportError(
                f"Row {row['row_number']}: manager {manager_email} was not found in the directory."
            )
        employee.manager = manager

    return DirectoryImportResult(created=created, updated=updated, total_rows=len(prepared_rows))

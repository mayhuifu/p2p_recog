from __future__ import annotations

from flask import Flask, flash, redirect, render_template, request, url_for

from .db import session_scope
from .employee_directory import DirectoryImportError, get_employee, import_employees_from_csv, list_employees, list_managers
from .models import Employee


ROLE_OPTIONS = [
    ("employee", "Employee"),
    ("manager", "Manager"),
    ("admin", "Admin"),
    ("executive", "Executive"),
]


def register_routes(app: Flask) -> None:
    @app.get("/")
    def index():
        with session_scope(app) as session:
            employees = list_employees(session)
            active_count = sum(1 for employee in employees if employee.is_active)
            manager_count = sum(1 for employee in employees if employee.role == "manager")
            region_count = len({employee.region for employee in employees if employee.region})
        return render_template(
            "index.html",
            employee_count=len(employees),
            active_count=active_count,
            manager_count=manager_count,
            region_count=region_count,
        )

    @app.get("/admin/employees")
    def admin_employees():
        with session_scope(app) as session:
            employees = list_employees(session)
        return render_template("admin_employees.html", employees=employees)

    @app.route("/admin/employees/new", methods=["GET", "POST"])
    def new_employee():
        with session_scope(app) as session:
            employee = Employee(name="", email="", role="employee", is_active=True)
            managers = list_managers(session)
            if request.method == "POST":
                _apply_employee_form(employee, request.form, managers)
                session.add(employee)
                flash(f"Created employee record for {employee.name}.", "success")
                return redirect(url_for("admin_employees"))

        return render_template(
            "employee_form.html",
            employee=employee,
            managers=managers,
            role_options=ROLE_OPTIONS,
            page_title="Create employee",
            submit_label="Create employee",
        )

    @app.route("/admin/employees/<int:employee_id>/edit", methods=["GET", "POST"])
    def edit_employee(employee_id: int):
        with session_scope(app) as session:
            employee = get_employee(session, employee_id)
            if employee is None:
                flash("Employee not found.", "danger")
                return redirect(url_for("admin_employees"))

            managers = [manager for manager in list_managers(session) if manager.id != employee.id]
            if request.method == "POST":
                _apply_employee_form(employee, request.form, managers)
                flash(f"Updated employee record for {employee.name}.", "success")
                return redirect(url_for("admin_employees"))

        return render_template(
            "employee_form.html",
            employee=employee,
            managers=managers,
            role_options=ROLE_OPTIONS,
            page_title=f"Edit {employee.name}",
            submit_label="Save changes",
        )

    @app.route("/admin/employees/import", methods=["GET", "POST"])
    def import_employees():
        example_csv = (
            "name,email,role,department,region,active,manager_email\n"
            "Ada Lovelace,ada@example.com,admin,Operations,US,yes,\n"
            "Grace Hopper,grace@example.com,manager,Engineering,US,yes,ada@example.com\n"
            "Alan Turing,alan@example.com,employee,Engineering,EU,yes,grace@example.com\n"
        )
        draft_csv = ""

        if request.method == "POST":
            draft_csv = request.form.get("csv_text", "").strip()
            upload = request.files.get("csv_file")
            if upload and upload.filename:
                draft_csv = upload.stream.read().decode("utf-8")

            try:
                with session_scope(app) as session:
                    result = import_employees_from_csv(session, draft_csv)
                flash(
                    f"Imported {result.total_rows} rows: {result.created} created, {result.updated} updated.",
                    "success",
                )
                return redirect(url_for("admin_employees"))
            except DirectoryImportError as exc:
                flash(str(exc), "danger")

        return render_template(
            "import_employees.html",
            draft_csv=draft_csv,
            example_csv=example_csv,
        )


def _apply_employee_form(employee: Employee, form, managers: list[Employee]) -> None:
    employee.name = form.get("name", "").strip()
    employee.email = form.get("email", "").strip().lower()
    employee.role = form.get("role", "employee").strip() or "employee"
    employee.department = form.get("department", "").strip() or None
    employee.region = form.get("region", "").strip() or None
    employee.is_active = form.get("is_active") == "on"

    manager_id = form.get("manager_id", "").strip()
    manager_lookup = {str(manager.id): manager for manager in managers}
    employee.manager = manager_lookup.get(manager_id)

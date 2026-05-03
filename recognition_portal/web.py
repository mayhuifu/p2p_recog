from __future__ import annotations

from flask import Flask, flash, g, redirect, render_template, request, session, url_for
from sqlalchemy import select

from .auth import (
    active_employee_required,
    build_session_user,
    consume_magic_link,
    create_magic_link_request,
    login_required,
    role_required,
)
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
        if getattr(g, "current_user", None) is not None:
            return redirect(url_for("portal_home"))
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

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if getattr(g, "current_user", None) is not None:
            return redirect(url_for("portal_home"))

        requested_email = ""
        if request.method == "POST":
            requested_email = request.form.get("email", "").strip().lower()
            try:
                with session_scope(app) as db_session:
                    create_magic_link_request(app, db_session, requested_email, request.remote_addr)
                flash("Check your email for a magic sign-in link.", "success")
                return redirect(url_for("login"))
            except ValueError as exc:
                flash(str(exc), "danger")

        return render_template("login.html", requested_email=requested_email)

    @app.get("/login/consume")
    def consume_login_token():
        raw_token = request.args.get("token", "").strip()
        if not raw_token:
            flash("That sign-in link is missing its token.", "danger")
            return redirect(url_for("login"))

        try:
            with session_scope(app) as db_session:
                token = consume_magic_link(db_session, raw_token)
                session_user = build_session_user(db_session, token.email)
        except ValueError as exc:
            flash(str(exc), "danger")
            return redirect(url_for("login"))

        session["user_session"] = {
            "email": session_user.email,
            "role": session_user.role,
            "access_state": session_user.access_state,
            "employee_id": session_user.employee_id,
            "display_name": session_user.display_name,
        }
        flash("You are now signed in.", "success")
        return redirect(url_for("portal_home"))

    @app.post("/logout")
    @login_required
    def logout():
        session.pop("user_session", None)
        flash("You have been signed out.", "success")
        return redirect(url_for("index"))

    @app.get("/portal")
    @login_required
    def portal_home():
        user = g.current_user
        employee = None
        if user.employee_id is not None:
            with session_scope(app) as db_session:
                employee = db_session.get(Employee, user.employee_id)
        return render_template("portal_home.html", user=user, employee=employee)

    @app.get("/admin/employees")
    @role_required("admin")
    def admin_employees():
        with session_scope(app) as session:
            employees = list_employees(session)
        return render_template("admin_employees.html", employees=employees)

    @app.route("/admin/employees/new", methods=["GET", "POST"])
    @role_required("admin")
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
    @role_required("admin")
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
    @role_required("admin")
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

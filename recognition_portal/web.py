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
from .recognitions import (
    COMPANY_VALUES,
    POINTS_PRESET_OPTIONS,
    RECOGNITION_CATEGORIES,
    PointsRecognitionError,
    PointsRecognitionInput,
    RecognitionCreateInput,
    RecognitionModerationError,
    RecognitionValidationError,
    cancel_points_recognition_request,
    can_moderate_recognition,
    create_non_monetary_recognition,
    create_points_recognition_request,
    delete_points_recognition_request,
    get_points_recognition_request_for_sender,
    list_all_recognitions_for_admin,
    list_employee_recognitions,
    list_feed_recognitions,
    list_points_recognition_requests_for_sender,
    moderate_recognition,
    update_points_recognition_request,
)


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
        context = _build_portal_context(app, user)
        return render_template(
            "portal_home.html",
            user=user,
            **context,
            recognition_categories=RECOGNITION_CATEGORIES,
            company_values=COMPANY_VALUES,
            points_preset_options=POINTS_PRESET_OPTIONS,
            non_monetary_form_data={"recipient_id": "", "category": "", "company_value": "", "message": ""},
            points_form_data={"recipient_ids": [], "category": "", "company_value": "", "message": "", "points": ""},
            can_moderate_recognition=can_moderate_recognition,
        )

    @app.post("/recognitions/non-monetary")
    @active_employee_required
    def submit_non_monetary_recognition():
        user = g.current_user
        form_data = {
            "recipient_id": request.form.get("recipient_id", "").strip(),
            "category": request.form.get("category", "").strip(),
            "company_value": request.form.get("company_value", "").strip(),
            "message": request.form.get("message", ""),
        }
        with session_scope(app) as db_session:
            try:
                create_non_monetary_recognition(
                    app,
                    db_session,
                    RecognitionCreateInput(
                        sender_id=user.employee_id,
                        recipient_id=int(form_data["recipient_id"]),
                        category=form_data["category"],
                        company_value=form_data["company_value"] or None,
                        message=form_data["message"],
                    ),
                )
                flash("Recognition published to the company feed.", "success")
                return redirect(url_for("portal_home"))
            except (ValueError, RecognitionValidationError) as exc:
                flash(str(exc), "danger")

        context = _build_portal_context(app, user)
        return render_template(
            "portal_home.html",
            user=user,
            **context,
            recognition_categories=RECOGNITION_CATEGORIES,
            company_values=COMPANY_VALUES,
            points_preset_options=POINTS_PRESET_OPTIONS,
            non_monetary_form_data=form_data,
            points_form_data={"recipient_ids": [], "category": "", "company_value": "", "message": "", "points": ""},
            can_moderate_recognition=can_moderate_recognition,
        )

    @app.post("/recognitions/points")
    @active_employee_required
    def submit_points_recognition():
        user = g.current_user
        form_data = {
            "recipient_ids": request.form.getlist("recipient_ids"),
            "category": request.form.get("category", "").strip(),
            "company_value": request.form.get("company_value", "").strip(),
            "message": request.form.get("message", ""),
            "points": request.form.get("points", "").strip(),
        }
        try:
            with session_scope(app) as db_session:
                create_points_recognition_request(
                    db_session,
                    PointsRecognitionInput(
                        sender_id=user.employee_id,
                        recipient_ids=[int(recipient_id) for recipient_id in form_data["recipient_ids"]],
                        category=form_data["category"],
                        company_value=form_data["company_value"] or None,
                        message=form_data["message"],
                        points=_coerce_points_value(form_data["points"]),
                    ),
                )
            flash("Points recognition submitted for manager approval.", "success")
            return redirect(url_for("portal_home"))
        except (ValueError, PointsRecognitionError) as exc:
            flash(str(exc), "danger")

        context = _build_portal_context(app, user)
        return render_template(
            "portal_home.html",
            user=user,
            **context,
            recognition_categories=RECOGNITION_CATEGORIES,
            company_values=COMPANY_VALUES,
            points_preset_options=POINTS_PRESET_OPTIONS,
            non_monetary_form_data={"recipient_id": "", "category": "", "company_value": "", "message": ""},
            points_form_data=form_data,
            can_moderate_recognition=can_moderate_recognition,
        )

    @app.route("/recognitions/points/<int:request_id>/edit", methods=["GET", "POST"])
    @active_employee_required
    def edit_points_recognition(request_id: int):
        user = g.current_user
        try:
            with session_scope(app) as db_session:
                request_record = get_points_recognition_request_for_sender(
                    db_session,
                    request_id=request_id,
                    sender_id=user.employee_id,
                )
                if request_record.status != "pending_approval":
                    flash("Only pending points recognitions can be edited.", "danger")
                    return redirect(url_for("portal_home"))
                employees = [
                    candidate
                    for candidate in list_employees(db_session)
                    if candidate.id != user.employee_id and candidate.can_participate
                ]
                form_data = {
                    "recipient_ids": [str(recipient.recipient_id) for recipient in request_record.recipients],
                    "category": request_record.category,
                    "company_value": request_record.company_value or "",
                    "message": request_record.message,
                    "points": str(request_record.requested_points_per_recipient),
                }
                if request.method == "POST":
                    form_data = {
                        "recipient_ids": request.form.getlist("recipient_ids"),
                        "category": request.form.get("category", "").strip(),
                        "company_value": request.form.get("company_value", "").strip(),
                        "message": request.form.get("message", ""),
                        "points": request.form.get("points", "").strip(),
                    }
                    try:
                        request_record = update_points_recognition_request(
                            db_session,
                            request_id=request_id,
                            sender_id=user.employee_id,
                            payload=PointsRecognitionInput(
                                sender_id=user.employee_id,
                                recipient_ids=[int(recipient_id) for recipient_id in form_data["recipient_ids"]],
                                category=form_data["category"],
                                company_value=form_data["company_value"] or None,
                                message=form_data["message"],
                                points=_coerce_points_value(form_data["points"]),
                            ),
                        )
                        flash("Pending points recognition updated.", "success")
                        return redirect(url_for("portal_home"))
                    except (ValueError, PointsRecognitionError) as exc:
                        flash(str(exc), "danger")
        except PointsRecognitionError as exc:
            flash(str(exc), "danger")
            return redirect(url_for("portal_home"))

        return render_template(
            "edit_points_recognition.html",
            user=user,
            request_record=request_record,
            employees=employees,
            recognition_categories=RECOGNITION_CATEGORIES,
            company_values=COMPANY_VALUES,
            points_preset_options=POINTS_PRESET_OPTIONS,
            form_data=form_data,
        )

    @app.post("/recognitions/points/<int:request_id>/cancel")
    @active_employee_required
    def cancel_points_recognition(request_id: int):
        user = g.current_user
        try:
            with session_scope(app) as db_session:
                cancel_points_recognition_request(
                    db_session,
                    request_id=request_id,
                    sender_id=user.employee_id,
                )
            flash("Pending points recognition canceled.", "success")
        except PointsRecognitionError as exc:
            flash(str(exc), "danger")
        return redirect(url_for("portal_home"))

    @app.post("/recognitions/points/<int:request_id>/delete")
    @active_employee_required
    def delete_points_recognition(request_id: int):
        user = g.current_user
        try:
            with session_scope(app) as db_session:
                delete_points_recognition_request(
                    db_session,
                    request_id=request_id,
                    sender_id=user.employee_id,
                )
            flash("Pending points recognition deleted.", "success")
        except PointsRecognitionError as exc:
            flash(str(exc), "danger")
        return redirect(url_for("portal_home"))

    @app.post("/recognitions/<int:recognition_id>/moderate")
    @active_employee_required
    def moderate_non_monetary_recognition(recognition_id: int):
        user = g.current_user
        action_type = request.form.get("action_type", "").strip()
        reason = request.form.get("reason", "").strip()
        try:
            with session_scope(app) as db_session:
                moderate_recognition(
                    app,
                    db_session,
                    recognition_id=recognition_id,
                    actor_id=user.employee_id,
                    action_type=action_type,
                    reason=reason,
                )
            flash(f"Recognition {action_type}.", "success")
        except RecognitionModerationError as exc:
            flash(str(exc), "danger")
        return redirect(url_for("portal_home"))

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


def _build_portal_context(app: Flask, user) -> dict:
    employee = None
    employees = []
    feed = []
    sent = []
    received = []
    moderation_queue = []
    points_requests = []
    if user.employee_id is not None:
        with session_scope(app) as db_session:
            employee = db_session.get(Employee, user.employee_id)
            if user.access_state == "active":
                employees = [
                    candidate
                    for candidate in list_employees(db_session)
                    if candidate.id != user.employee_id and candidate.can_participate
                ]
                feed = list_feed_recognitions(db_session)
                sent, received = list_employee_recognitions(db_session, user.employee_id)
                points_requests = list_points_recognition_requests_for_sender(
                    db_session,
                    sender_id=user.employee_id,
                )
                if user.role == "admin":
                    moderation_queue = list_all_recognitions_for_admin(db_session)
    return {
        "employee": employee,
        "employees": employees,
        "feed": feed,
        "sent": sent,
        "received": received,
        "moderation_queue": moderation_queue,
        "points_requests": points_requests,
    }


def _coerce_points_value(raw_value: str) -> int:
    value = raw_value.strip()
    if not value:
        raise PointsRecognitionError("Choose a valid points amount.")
    return int(value)

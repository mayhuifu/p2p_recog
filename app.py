import argparse
import os
import smtplib
import socket
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime
from email.message import EmailMessage
from typing import List, Optional, Tuple

import gradio as gr
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, create_engine, select
from sqlalchemy.orm import declarative_base, relationship, sessionmaker


# ---------- Database (SQLAlchemy ORM) ----------

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'instance', 'recognition.db')
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

engine = create_engine(
    f"sqlite:///{DB_PATH}", echo=False, future=True, connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
Base = declarative_base()


class Employee(Base):
    __tablename__ = 'employee'

    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    email = Column(String(100), unique=True, nullable=False)
    role = Column(String(50), nullable=False, default='employee')  # employee, manager, hr_director
    manager_id = Column(Integer, ForeignKey('employee.id'))

    manager = relationship('Employee', remote_side=[id], backref='reports')

    def __repr__(self) -> str:
        return f'<Employee {self.name}>'


class Recognition(Base):
    __tablename__ = 'recognition'

    id = Column(Integer, primary_key=True)
    submitter_id = Column(Integer, ForeignKey('employee.id'), nullable=False)
    recognized_id = Column(Integer, ForeignKey('employee.id'), nullable=False)
    reason = Column(Text, nullable=False)
    status = Column(String(50), nullable=False, default='pending_manager_approval')
    denial_reason = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

    submitter = relationship('Employee', foreign_keys=[submitter_id])
    recognized = relationship('Employee', foreign_keys=[recognized_id])


def init_db_with_seed_data() -> None:
    Base.metadata.create_all(engine)
    with SessionLocal() as session:
        count = session.scalar(select(Employee).count())
        if count and count > 0:
            return

        hr_director = Employee(name='HR Director', email='hr@company.com', role='hr_director')
        manager = Employee(name='Manager Mike', email='manager@company.com', role='manager')
        employee1 = Employee(name='Employee Alice', email='alice@company.com', manager=manager)
        employee2 = Employee(name='Employee Bob', email='bob@company.com', manager=manager)

        session.add_all([hr_director, manager, employee1, employee2])
        session.commit()


# ---------- Simplified Email Notification ----------

def send_notification(subject: str, recipients: List[str], body: str) -> None:
    smtp_host = os.getenv('SMTP_HOST')
    smtp_port = int(os.getenv('SMTP_PORT', '587'))
    smtp_user = os.getenv('SMTP_USER')
    smtp_pass = os.getenv('SMTP_PASS')
    smtp_sender = os.getenv('SMTP_SENDER', smtp_user or 'noreply@example.com')

    if not smtp_host or not smtp_user or not smtp_pass:
        print(f"[NOTIFY] {subject}\nTo: {', '.join(recipients)}\n{body}")
        return

    msg = EmailMessage()
    msg['Subject'] = subject
    msg['From'] = smtp_sender
    msg['To'] = ', '.join(recipients)
    msg.set_content(body)

    try:
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.send_message(msg)
    except Exception as exc:  # best-effort
        print(f"[NOTIFY][ERROR] {exc}. Falling back to console log.")
        print(f"[NOTIFY] {subject}\nTo: {', '.join(recipients)}\n{body}")


# ---------- Helpers ----------

def get_available_port(preferred_port: int, max_tries: int = 10) -> int:
    port = preferred_port
    for _ in range(max_tries):
        if is_port_free(port):
            return port
        port += 1
    return preferred_port  # fallback, gradio will error if still not free


def is_port_free(port: int) -> bool:
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(('0.0.0.0', port))
            return True
        except OSError:
            return False


def list_employees(session, exclude_id: Optional[int] = None) -> List[Tuple[str, int]]:
    stmt = select(Employee)
    employees = session.scalars(stmt).all()
    result: List[Tuple[str, int]] = []
    for emp in employees:
        if exclude_id is not None and emp.id == exclude_id:
            continue
        result.append((f"{emp.name} <{emp.email}>", emp.id))
    return result


def get_hr_director(session) -> Optional[Employee]:
    return session.scalars(select(Employee).where(Employee.role == 'hr_director')).first()


# ---------- Gradio App ----------

@dataclass
class UserState:
    id: int
    name: str
    email: str
    role: str


def handle_login(email: str, state: Optional[UserState]):
    with SessionLocal() as session:
        user = session.scalars(select(Employee).where(Employee.email == email)).first()
        if not user:
            return gr.update(value="Invalid email address."), None, gr.update(visible=False), gr.update(visible=False), gr.update(visible=False)
        new_state = UserState(id=user.id, name=user.name, email=user.email, role=user.role)
        welcome = f"Logged in as {user.name} ({user.role})."
        return welcome, new_state, gr.update(visible=True), gr.update(visible=True), gr.update(visible=True)


def handle_logout(state: Optional[UserState]):
    return "Logged out.", None, gr.update(visible=False), gr.update(visible=False), gr.update(visible=False)


def refresh_employees_dropdown(state: Optional[UserState]):
    with SessionLocal() as session:
        choices = list_employees(session, exclude_id=state.id if state else None)
        return gr.update(choices=choices, value=None)


def submit_recognition(recognized_emp_id: Optional[int], reason: str, state: Optional[UserState]):
    if not state:
        return "Please log in first."
    if not recognized_emp_id or not reason.strip():
        return "Please select an employee and provide a reason."

    with SessionLocal() as session:
        submitter = session.get(Employee, state.id)
        recognized = session.get(Employee, int(recognized_emp_id))
        if not submitter or not recognized:
            return "Invalid selection."

        rec = Recognition(
            submitter_id=submitter.id,
            recognized_id=recognized.id,
            reason=reason.strip(),
            status='pending_manager_approval'
        )
        session.add(rec)
        session.commit()

        if submitter.manager is not None:
            send_notification(
                subject='New Recognition Request for Approval',
                recipients=[submitter.manager.email],
                body=(
                    f"A new recognition request from {submitter.name} for {recognized.name} "
                    f"is waiting for your approval."
                ),
            )

    return "Recognition submitted successfully!"


def get_pending_for_user(state: Optional[UserState]):
    if not state:
        return gr.update(choices=[], value=None), gr.update(visible=False), gr.update(visible=False), gr.update(visible=False)
    with SessionLocal() as session:
        if state.role == 'manager':
            # pending manager approvals where submitter's manager is current user
            stmt = (
                select(Recognition)
                .join(Employee, Recognition.submitter_id == Employee.id)
                .where(Recognition.status == 'pending_manager_approval')
                .where(Employee.manager_id == state.id)
            )
        elif state.role == 'hr_director':
            stmt = select(Recognition).where(Recognition.status == 'pending_hr_approval')
        else:
            return gr.update(choices=[], value=None), gr.update(visible=False), gr.update(visible=False), gr.update(visible=False)

        recs = session.scalars(stmt).all()
        choices: List[Tuple[str, int]] = []
        for r in recs:
            label = f"#{r.id} From: {r.submitter.name} -> To: {r.recognized.name} | {r.reason[:60]}{'...' if len(r.reason) > 60 else ''}"
            choices.append((label, r.id))

        # For manager show both approve/deny + denial reason
        is_manager = state.role == 'manager'
        return (
            gr.update(choices=choices, value=None),
            gr.update(visible=is_manager),
            gr.update(visible=True),
            gr.update(visible=is_manager),
        )


def approve_selected(recognition_id: Optional[int], state: Optional[UserState]):
    if not state:
        return "Please log in first."
    if not recognition_id:
        return "Select a recognition to approve."
    with SessionLocal() as session:
        rec = session.get(Recognition, int(recognition_id))
        if not rec:
            return "Invalid recognition."
        if state.role != 'manager':
            return "Only managers can approve at this stage."
        rec.status = 'pending_hr_approval'
        session.commit()

        hr = get_hr_director(session)
        if hr:
            send_notification(
                subject='Recognition Approved - Action Required',
                recipients=[hr.email],
                body=(
                    f"The recognition for {rec.recognized.name} submitted by {rec.submitter.name} "
                    f"has been approved and is pending a gift card issuance."
                ),
            )
        send_notification(
            subject='You have been recognized!',
            recipients=[rec.recognized.email],
            body=(
                f"Congratulations! You have been recognized by {rec.submitter.name}. "
                f"Reason: {rec.reason}"
            ),
        )
    return "Recognition moved to HR for finalization."


def deny_selected(recognition_id: Optional[int], denial_reason: str, state: Optional[UserState]):
    if not state:
        return "Please log in first."
    if not recognition_id:
        return "Select a recognition to deny."
    if not denial_reason.strip():
        return "Provide a denial reason."
    with SessionLocal() as session:
        rec = session.get(Recognition, int(recognition_id))
        if not rec:
            return "Invalid recognition."
        if state.role != 'manager':
            return "Only managers can deny at this stage."
        rec.status = 'denied'
        rec.denial_reason = denial_reason.strip()
        session.commit()
        send_notification(
            subject='Recognition Request Denied',
            recipients=[rec.submitter.email],
            body=(
                f"Your recognition request for {rec.recognized.name} was denied. "
                f"Reason: {rec.denial_reason}"
            ),
        )
    return "Recognition denied."


def issue_gift_card(recognition_id: Optional[int], state: Optional[UserState]):
    if not state:
        return "Please log in first."
    if state.role != 'hr_director':
        return "Only HR Director can issue gift cards."
    if not recognition_id:
        return "Select a recognition to finalize."
    with SessionLocal() as session:
        rec = session.get(Recognition, int(recognition_id))
        if not rec:
            return "Invalid recognition."
        rec.status = 'completed'
        session.commit()
    return "Gift card issued and recognition completed."


def build_interface():
    with gr.Blocks(title="Peer-to-Peer Recognition") as demo:
        state = gr.State(value=None)  # UserState | None

        gr.Markdown("**Peer-to-Peer Recognition System**")

        with gr.Row():
            email_in = gr.Textbox(label="Login with Email", placeholder="you@company.com")
            login_btn = gr.Button("Login")
            logout_btn = gr.Button("Logout")

        login_status = gr.Markdown(visible=True)

        with gr.Tab("Recognize", visible=False) as tab_recognize:
            recognize_employee = gr.Dropdown(label="Select Employee", choices=[])
            recognize_reason = gr.Textbox(label="Reason", lines=3)
            recognize_btn = gr.Button("Submit Recognition")
            recognize_status = gr.Markdown()

        with gr.Tab("Approvals", visible=False) as tab_approvals:
            pending_dropdown = gr.Dropdown(label="Pending Recognitions", choices=[])
            with gr.Row():
                approve_btn = gr.Button("Approve")
                deny_btn = gr.Button("Deny")
                denial_reason = gr.Textbox(label="Denial Reason", lines=2)
            approvals_status = gr.Markdown()

        with gr.Tab("HR Finalization", visible=False) as tab_hr:
            hr_pending_dropdown = gr.Dropdown(label="Pending HR Recognitions", choices=[])
            hr_issue_btn = gr.Button("Issue Gift Card")
            hr_status = gr.Markdown()

        # Events
        login_btn.click(
            fn=handle_login,
            inputs=[email_in, state],
            outputs=[login_status, state, tab_recognize, tab_approvals, tab_hr],
        ).then(
            fn=refresh_employees_dropdown,
            inputs=[state],
            outputs=[recognize_employee],
        ).then(
            fn=get_pending_for_user,
            inputs=[state],
            outputs=[pending_dropdown, denial_reason, hr_pending_dropdown, approve_btn],
        )

        logout_btn.click(
            fn=handle_logout,
            inputs=[state],
            outputs=[login_status, state, tab_recognize, tab_approvals, tab_hr],
        )

        recognize_btn.click(
            fn=submit_recognition,
            inputs=[recognize_employee, recognize_reason, state],
            outputs=[recognize_status],
        ).then(
            fn=get_pending_for_user,
            inputs=[state],
            outputs=[pending_dropdown, denial_reason, hr_pending_dropdown, approve_btn],
        )

        approve_btn.click(
            fn=approve_selected,
            inputs=[pending_dropdown, state],
            outputs=[approvals_status],
        ).then(
            fn=get_pending_for_user,
            inputs=[state],
            outputs=[pending_dropdown, denial_reason, hr_pending_dropdown, approve_btn],
        )

        deny_btn.click(
            fn=deny_selected,
            inputs=[pending_dropdown, denial_reason, state],
            outputs=[approvals_status],
        ).then(
            fn=get_pending_for_user,
            inputs=[state],
            outputs=[pending_dropdown, denial_reason, hr_pending_dropdown, approve_btn],
        )

        hr_issue_btn.click(
            fn=issue_gift_card,
            inputs=[hr_pending_dropdown, state],
            outputs=[hr_status],
        ).then(
            fn=get_pending_for_user,
            inputs=[state],
            outputs=[pending_dropdown, denial_reason, hr_pending_dropdown, approve_btn],
        )

        return demo


def main():
    parser = argparse.ArgumentParser(description='Peer-to-Peer Recognition (Gradio)')
    parser.add_argument('--host', default='0.0.0.0')
    parser.add_argument('--port', type=int, default=int(os.getenv('PORT', '7860')))
    parser.add_argument('--inbrowser', action='store_true', help='Open in browser on start')
    args = parser.parse_args()

    init_db_with_seed_data()

    port = get_available_port(args.port)
    if port != args.port:
        print(f"Port {args.port} is in use. Using {port} instead.")

    demo = build_interface()
    demo.launch(server_name=args.host, server_port=port, inbrowser=args.inbrowser, show_error=True)


if __name__ == '__main__':
    main()
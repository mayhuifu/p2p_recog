import gradio as gr
from recognition import Recognition

# Initialize the Recognition system
recognition_system = Recognition()

# Current user session
current_user = {"email": None, "role": None}

def login(email):
    """Handle user login and return appropriate interface based on role"""
    if recognition_system.login(email):
        current_user["email"] = email
        current_user["role"] = recognition_system.get_employee_role(email)
        
        if current_user["role"] == "employee":
            return f"Logged in as Employee: {email}", gr.update(visible=True), gr.update(visible=False), gr.update(visible=False)
        elif current_user["role"] == "manager":
            pending_requests = recognition_system.view_pending_requests(email)
            pending_html = ""
            if pending_requests:
                pending_html = "<h3>Pending Approval Requests:</h3>"
                for req in pending_requests:
                    pending_html += f"<div style='border: 1px solid #ccc; padding: 10px; margin-bottom: 10px;'>"
                    pending_html += f"ID: {req['id']}<br>"
                    pending_html += f"From: {req['from_email']}<br>"
                    pending_html += f"To: {req['to_email']}<br>"
                    pending_html += f"Reason: {req['reason']}<br>"
                    pending_html += "</div>"
            else:
                pending_html = "<p>No pending requests</p>"
                
            return f"Logged in as Manager: {email}", gr.update(visible=True), gr.update(visible=True, value=pending_html), gr.update(visible=False)
        elif current_user["role"] == "hr_director":
            todo_list = recognition_system.get_hr_todo_list()
            todo_html = ""
            if todo_list:
                todo_html = "<h3>To-Do List (Gift Cards to Issue):</h3>"
                for todo in todo_list:
                    todo_html += f"<div style='border: 1px solid #ccc; padding: 10px; margin-bottom: 10px;'>"
                    todo_html += f"ID: {todo['id']}<br>"
                    todo_html += f"Employee: {todo['employee_email']}<br>"
                    todo_html += f"Reason: {todo['reason']}<br>"
                    todo_html += f"Status: {todo['status']}<br>"
                    todo_html += "</div>"
            else:
                todo_html = "<p>No pending gift cards to issue</p>"
                
            # Also show transaction records
            records = recognition_system.get_transaction_records()
            records_html = ""
            if records:
                records_html = "<h3>Transaction Records:</h3>"
                for record in records:
                    records_html += f"<div style='border: 1px solid #ccc; padding: 10px; margin-bottom: 10px;'>"
                    records_html += f"Time: {record['timestamp']}<br>"
                    records_html += f"From: {record['from_email']}<br>"
                    records_html += f"To: {record['to_email']}<br>"
                    records_html += f"Status: {record['status']}<br>"
                    records_html += f"Reason: {record['reason']}<br>"
                    records_html += "</div>"
            else:
                records_html = "<p>No transaction records</p>"
                
            hr_html = todo_html + "<br><br>" + records_html
            return f"Logged in as HR Director: {email}", gr.update(visible=True), gr.update(visible=False), gr.update(visible=True, value=hr_html)
    else:
        return "Invalid email. Please try again.", gr.update(visible=False), gr.update(visible=False), gr.update(visible=False)

def submit_recognition(to_email, reason):
    """Submit a recognition request"""
    if current_user["email"]:
        if recognition_system.submit_recognition(current_user["email"], to_email, reason):
            return f"Recognition submitted successfully for {to_email}!"
        else:
            return f"Failed to submit recognition. Please check the email address."
    else:
        return "Please log in first."

def handle_approval(request_id, action, denial_reason=""):
    """Handle approval or denial of recognition requests"""
    if current_user["email"] and current_user["role"] == "manager":
        request_id = int(request_id)
        if action == "approve":
            if recognition_system.approve_recognition(current_user["email"], request_id):
                # Refresh the pending requests view
                pending_requests = recognition_system.view_pending_requests(current_user["email"])
                pending_html = ""
                if pending_requests:
                    pending_html = "<h3>Pending Approval Requests:</h3>"
                    for req in pending_requests:
                        pending_html += f"<div style='border: 1px solid #ccc; padding: 10px; margin-bottom: 10px;'>"
                        pending_html += f"ID: {req['id']}<br>"
                        pending_html += f"From: {req['from_email']}<br>"
                        pending_html += f"To: {req['to_email']}<br>"
                        pending_html += f"Reason: {req['reason']}<br>"
                        pending_html += "</div>"
                else:
                    pending_html = "<p>No pending requests</p>"
                    
                return f"Request {request_id} approved successfully!", gr.update(value=pending_html)
            else:
                return f"Failed to approve request {request_id}.", gr.update()
        elif action == "deny":
            if recognition_system.deny_recognition(current_user["email"], request_id, denial_reason):
                # Refresh the pending requests view
                pending_requests = recognition_system.view_pending_requests(current_user["email"])
                pending_html = ""
                if pending_requests:
                    pending_html = "<h3>Pending Approval Requests:</h3>"
                    for req in pending_requests:
                        pending_html += f"<div style='border: 1px solid #ccc; padding: 10px; margin-bottom: 10px;'>"
                        pending_html += f"ID: {req['id']}<br>"
                        pending_html += f"From: {req['from_email']}<br>"
                        pending_html += f"To: {req['to_email']}<br>"
                        pending_html += f"Reason: {req['reason']}<br>"
                        pending_html += "</div>"
                else:
                    pending_html = "<p>No pending requests</p>"
                    
                return f"Request {request_id} denied with reason: {denial_reason}", gr.update(value=pending_html)
            else:
                return f"Failed to deny request {request_id}.", gr.update()
    else:
        return "You must be logged in as a manager to perform this action.", gr.update()

def refresh_hr_todo_list():
    """Refresh the HR Director's to-do list"""
    if current_user["email"] and current_user["role"] == "hr_director":
        todo_list = recognition_system.get_hr_todo_list()
        todo_html = ""
        if todo_list:
            todo_html = "<h3>To-Do List (Gift Cards to Issue):</h3>"
            for todo in todo_list:
                todo_html += f"<div style='border: 1px solid #ccc; padding: 10px; margin-bottom: 10px;'>"
                todo_html += f"ID: {todo['id']}<br>"
                todo_html += f"Employee: {todo['employee_email']}<br>"
                todo_html += f"Reason: {todo['reason']}<br>"
                todo_html += f"Status: {todo['status']}<br>"
                todo_html += "</div>"
        else:
            todo_html = "<p>No pending gift cards to issue</p>"
            
        # Also show transaction records
        records = recognition_system.get_transaction_records()
        records_html = ""
        if records:
            records_html = "<h3>Transaction Records:</h3>"
            for record in records:
                records_html += f"<div style='border: 1px solid #ccc; padding: 10px; margin-bottom: 10px;'>"
                records_html += f"Time: {record['timestamp']}<br>"
                records_html += f"From: {record['from_email']}<br>"
                records_html += f"To: {record['to_email']}<br>"
                records_html += f"Status: {record['status']}<br>"
                records_html += f"Reason: {record['reason']}<br>"
                records_html += "</div>"
        else:
            records_html = "<p>No transaction records</p>"
            
        hr_html = todo_html + "<br><br>" + records_html
        return "HR to-do list refreshed", gr.update(value=hr_html)
    else:
        return "You must be logged in as HR Director to perform this action.", gr.update()

with gr.Blocks(title="Peer Recognition System") as demo:
    gr.Markdown("# Company Peer Recognition System")
    
    with gr.Row():
        with gr.Column():
            gr.Markdown("## Login")
            email_input = gr.Textbox(label="Email Address", placeholder="Enter your company email")
            login_button = gr.Button("Login")
            login_message = gr.Textbox(label="Status", interactive=False)
    
    # Employee recognition form
    with gr.Row(visible=False) as employee_section:
        with gr.Column():
            gr.Markdown("## Submit Recognition")
            recognize_email = gr.Textbox(label="Colleague's Email", placeholder="Enter colleague's email to recognize")
            recognize_reason = gr.Textbox(label="Reason for Recognition", placeholder="Why do you want to recognize this colleague?", lines=5)
            submit_button = gr.Button("Submit Recognition")
            recognition_message = gr.Textbox(label="Recognition Status", interactive=False)
    
    # Manager approval section
    with gr.Row(visible=False) as manager_section:
        with gr.Column():
            gr.Markdown("## Manager Approval Dashboard")
            pending_requests_html = gr.HTML(label="Pending Requests")
            
            with gr.Row():
                request_id_input = gr.Textbox(label="Request ID", placeholder="Enter the request ID to approve/deny")
                approval_action = gr.Radio(["approve", "deny"], label="Action")
            
            denial_reason = gr.Textbox(label="Denial Reason (if denying)", placeholder="Provide a reason for denial", lines=3)
            process_button = gr.Button("Process Request")
            manager_message = gr.Textbox(label="Process Status", interactive=False)
    
    # HR Director section
    with gr.Row(visible=False) as hr_section:
        with gr.Column():
            gr.Markdown("## HR Director Dashboard")
            hr_dashboard_html = gr.HTML(label="HR To-Do List & Transaction Records")
            refresh_button = gr.Button("Refresh Data")
            hr_message = gr.Textbox(label="Status", interactive=False)
    
    # Set up events
    login_button.click(
        fn=login,
        inputs=[email_input],
        outputs=[login_message, employee_section, manager_section, hr_section]
    )
    
    submit_button.click(
        fn=submit_recognition,
        inputs=[recognize_email, recognize_reason],
        outputs=[recognition_message]
    )
    
    process_button.click(
        fn=handle_approval,
        inputs=[request_id_input, approval_action, denial_reason],
        outputs=[manager_message, pending_requests_html]
    )
    
    refresh_button.click(
        fn=refresh_hr_todo_list,
        inputs=[],
        outputs=[hr_message, hr_dashboard_html]
    )

if __name__ == "__main__":
    demo.launch()
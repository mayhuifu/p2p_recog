import datetime

class Recognition:
    def __init__(self):
        # Initialize with default users and roles
        self.employees = [
            {"email": "hui.fu@umsemi.com", "role": "employee", "manager": "hui.fu@ieee.org"},
            {"email": "hui.fu@ieee.org", "role": "manager", "manager": "mayhuifu@gmail.com"},
            {"email": "mayhuifu@gmail.com", "role": "hr_director", "manager": None}
        ]
        # List to store all recognition requests
        self.recognitions = []
        # Dictionary to map manager emails to their pending recognition requests
        self.pending_requests = {}
        # List for HR Director's to-do list
        self.hr_todo_list = []
        # List to store all transaction records
        self.transaction_records = []
        # Initialize request counter
        self.request_counter = 0
        
    def validate_email(self, email: str) -> bool:
        """Validates if an email belongs to a valid employee"""
        # Check if email is in the employees list
        for employee in self.employees:
            if employee["email"] == email:
                return True
        return False

    def login(self, email: str) -> bool:
        """Allows a user to log in if they have a valid company email"""
        return self.validate_email(email)

    def get_employee_role(self, email: str) -> str:
        """Returns the role of an employee"""
        for employee in self.employees:
            if employee["email"] == email:
                return employee["role"]
        return None

    def get_employee_manager(self, email: str) -> str:
        """Returns the manager's email of an employee"""
        for employee in self.employees:
            if employee["email"] == email:
                return employee["manager"]
        return None
        
    def submit_recognition(self, from_email: str, to_email: str, reason: str) -> bool:
        """Allows an employee to recognize another employee with a reason"""
        # Validate both emails
        if not self.validate_email(from_email) or not self.validate_email(to_email):
            return False
            
        # Check that employees are not the same person
        if from_email == to_email:
            return False
            
        # Create recognition request
        self.request_counter += 1
        request_id = self.request_counter
        
        # Get the manager of the employee who is submitting the recognition
        manager_email = self.get_employee_manager(from_email)
        
        recognition = {
            "id": request_id,
            "from_email": from_email,
            "to_email": to_email,
            "reason": reason,
            "status": "pending",
            "manager_email": manager_email,
            "denial_reason": None
        }
        
        # Add to recognitions list
        self.recognitions.append(recognition)
        
        # Add to pending requests for the manager
        if manager_email not in self.pending_requests:
            self.pending_requests[manager_email] = []
        self.pending_requests[manager_email].append(request_id)
        
        # Notify manager and HR
        self.notify_manager_and_hr(from_email, to_email, request_id)
        
        # Record transaction
        self.record_transaction(from_email, to_email, "submitted", reason)
        
        return True
        
    def notify_manager_and_hr(self, from_email: str, to_email: str, request_id: int):
        """Sends a notification to the manager and HR Director regarding the recognition request"""
        manager_email = self.get_employee_manager(from_email)
        hr_director_email = None
        
        # Find HR director's email
        for employee in self.employees:
            if employee["role"] == "hr_director":
                hr_director_email = employee["email"]
                break
                
        if manager_email:
            print(f"Notification sent to manager {manager_email} about recognition request {request_id}")
            # In a real system, this would send an actual email or notification
            
        if hr_director_email:
            print(f"Notification sent to HR Director {hr_director_email} about recognition request {request_id}")
            # In a real system, this would send an actual email or notification
            
    def view_pending_requests(self, manager_email: str) -> list:
        """Allows a manager to view all pending recognition requests"""
        if not self.validate_email(manager_email) or self.get_employee_role(manager_email) != "manager":
            return []
            
        if manager_email not in self.pending_requests:
            return []
            
        pending_request_ids = self.pending_requests[manager_email]
        pending_requests = []
        
        for request_id in pending_request_ids:
            for recognition in self.recognitions:
                if recognition["id"] == request_id and recognition["status"] == "pending":
                    pending_requests.append(recognition)
                    
        return pending_requests

    def approve_recognition(self, manager_email: str, request_id: int) -> bool:
        """Approves a recognition request and generates recognition letters"""
        # Validate manager
        if not self.validate_email(manager_email) or self.get_employee_role(manager_email) != "manager":
            return False
            
        # Find the recognition request
        recognition = None
        for rec in self.recognitions:
            if rec["id"] == request_id and rec["status"] == "pending":
                recognition = rec
                break
                
        if not recognition or recognition["manager_email"] != manager_email:
            return False
            
        # Update recognition status
        recognition["status"] = "approved"
        
        # Remove from pending requests
        if manager_email in self.pending_requests and request_id in self.pending_requests[manager_email]:
            self.pending_requests[manager_email].remove(request_id)
            
        # Generate recognition letters
        self.generate_letters(recognition["to_email"], "approved", recognition["reason"])
        
        # Update HR to-do list
        self.update_hr_todo_list(request_id)
        
        # Record transaction
        self.record_transaction(recognition["from_email"], recognition["to_email"], "approved", recognition["reason"])
        
        return True

    def deny_recognition(self, manager_email: str, request_id: int, reason: str) -> bool:
        """Denies a recognition request, providing a reason, and generates denial letters"""
        # Validate manager
        if not self.validate_email(manager_email) or self.get_employee_role(manager_email) != "manager":
            return False
            
        # Find the recognition request
        recognition = None
        for rec in self.recognitions:
            if rec["id"] == request_id and rec["status"] == "pending":
                recognition = rec
                break
                
        if not recognition or recognition["manager_email"] != manager_email:
            return False
            
        # Update recognition status and denial reason
        recognition["status"] = "denied"
        recognition["denial_reason"] = reason
        
        # Remove from pending requests
        if manager_email in self.pending_requests and request_id in self.pending_requests[manager_email]:
            self.pending_requests[manager_email].remove(request_id)
            
        # Generate denial letters
        self.generate_letters(recognition["from_email"], "denied", reason)
        
        # Record transaction
        self.record_transaction(recognition["from_email"], recognition["to_email"], "denied", reason)
        
        return True

    def update_hr_todo_list(self, request_id: int):
        """Updates the HR Director's to-do list with approved recognitions for gift card issuance"""
        # Find the recognition request
        recognition = None
        for rec in self.recognitions:
            if rec["id"] == request_id and rec["status"] == "approved":
                recognition = rec
                break
                
        if not recognition:
            return
            
        # Add to HR to-do list
        hr_todo_item = {
            "id": request_id,
            "employee_email": recognition["to_email"],
            "reason": recognition["reason"],
            "status": "pending_gift_card"
        }
        
        self.hr_todo_list.append(hr_todo_item)
        
        # Find HR director's email
        hr_director_email = None
        for employee in self.employees:
            if employee["role"] == "hr_director":
                hr_director_email = employee["email"]
                break
                
        if hr_director_email:
            print(f"Added to HR Director's to-do list: Issue gift card for recognition {request_id}")
            # In a real system, this would send an actual notification
            
    def record_transaction(self, from_email: str, to_email: str, status: str, reason: str):
        """Records all transactions related to recognition in the system"""
        transaction = {
            "timestamp": datetime.datetime.now(),
            "from_email": from_email,
            "to_email": to_email,
            "status": status,
            "reason": reason
        }
        
        self.transaction_records.append(transaction)
        
    def generate_letters(self, recipient_email: str, result: str, reason: str):
        """Generates the necessary letters for both approvals and denials of recognition"""
        hr_director_email = None
        for employee in self.employees:
            if employee["role"] == "hr_director":
                hr_director_email = employee["email"]
                break
                
        if result == "approved":
            # Generate recognition letter to the recognized employee
            print(f"\nRecognition Letter to: {recipient_email}")
            print("Congratulations! Your colleague has recognized your outstanding contribution.")
            print(f"Reason: {reason}")
            print("Your manager and the HR Director have been notified.\n")
            
            # Notify the employee's manager
            manager_email = self.get_employee_manager(recipient_email)
            if manager_email:
                print(f"Notification to manager {manager_email}:")
                print(f"Your team member {recipient_email} has been recognized for their outstanding contribution.")
                print(f"Reason: {reason}\n")
                
            # Notify HR Director
            if hr_director_email:
                print(f"Notification to HR Director {hr_director_email}:")
                print(f"Employee {recipient_email} has been recognized for their outstanding contribution.")
                print(f"Reason: {reason}")
                print("Please issue a gift card.\n")
                
        elif result == "denied":
            # Generate denial letter to the employee who submitted the request
            print(f"\nDenial Letter to: {recipient_email}")
            print("Your recognition request has been reviewed but could not be approved at this time.")
            print(f"Reason for denial: {reason}")
            print("Your manager and the HR Director have been notified.\n")
            
            # Notify the employee's manager
            manager_email = self.get_employee_manager(recipient_email)
            if manager_email:
                print(f"Notification to manager {manager_email}:")
                print(f"A recognition request from your team member {recipient_email} has been denied.")
                print(f"Reason for denial: {reason}\n")
                
            # Notify HR Director
            if hr_director_email:
                print(f"Notification to HR Director {hr_director_email}:")
                print(f"A recognition request from employee {recipient_email} has been denied.")
                print(f"Reason for denial: {reason}\n")
                
    def get_transaction_records(self) -> list:
        """Returns all transaction records"""
        return self.transaction_records
        
    def get_hr_todo_list(self) -> list:
        """Returns the HR Director's to-do list"""
        return self.hr_todo_list
        
    def add_employee(self, email: str, role: str, manager_email: str = None) -> bool:
        """Adds a new employee to the system"""
        # Check if employee already exists
        for employee in self.employees:
            if employee["email"] == email:
                return False
                
        # Validate manager email if provided
        if manager_email and not self.validate_email(manager_email):
            return False
            
        # Add new employee
        new_employee = {
            "email": email,
            "role": role,
            "manager": manager_email
        }
        
        self.employees.append(new_employee)
        return True
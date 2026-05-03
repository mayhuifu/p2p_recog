#!/usr/bin/env python
import warnings
import os
from datetime import datetime

from p2precog.crew import EngineeringTeam

warnings.filterwarnings("ignore", category=SyntaxWarning, module="pysbd")

# Create output directory if it doesn't exist
os.makedirs('output', exist_ok=True)

requirements = """
A simple peer to peer recognization management system for a company.
The system should be able to verify the user is a valid company employee via email address 
The system should allow users to login with their email from the company. 
The system should be able to validate the user's email address.
The system should allow users to regonize any other employee with a reason.
The system should generate a email or pushover notification to his own manager and HR DIRECTOR.
The system should be able to register the pending approval request for the manager when he/she login and see the pending requests.
The system should be able to generate a recognition letter to the named employee, his manager and HR DIRECTOR once approved by the manager
The system should be able to generate a letter to the employee who submit the request on reason of deny the recognization, his manager and HR DIRECTOR once denied by the manager
The system will put the approved recognization into HR directors to Do list to issue a gift card.
The system should be able to put a record for all transaction for all employee, manager and HR directos
 The initial role with the system will be employee email: hui.fu@umsemi.com, manager email: hui.fu@ieee.org and HR director email: mayhuifu@gmail.com
"""
module_name = "recognition.py"
class_name = "Recognition"


def run():
    """
    Run the research crew.
    """
    inputs = {
        'requirements': requirements,
        'module_name': module_name,
        'class_name': class_name
    }

    # Create and run the crew
    result = EngineeringTeam().crew().kickoff(inputs=inputs)


if __name__ == "__main__":
    run()
import argparse

from recognition_portal import create_app
from recognition_portal.notifications import send_smtp_test_email, verify_smtp_connection


def main() -> None:
    parser = argparse.ArgumentParser(description="P2P Recognition portal")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=5000)
    parser.add_argument("--debug", action="store_true")
    parser.add_argument(
        "--smtp-test",
        action="store_true",
        help="Verify SMTP connection/login and exit.",
    )
    parser.add_argument(
        "--smtp-test-to",
        help="Send a real SMTP test email to the given recipient and exit.",
    )
    args = parser.parse_args()

    app = create_app()
    if args.smtp_test or args.smtp_test_to:
        if args.smtp_test_to:
            send_smtp_test_email(app, args.smtp_test_to)
            print(f"SMTP test email sent to {args.smtp_test_to}.")
        else:
            verify_smtp_connection(app)
            print("SMTP connection and login succeeded.")
        return

    app.run(host=args.host, port=args.port, debug=args.debug)


if __name__ == "__main__":
    main()

import argparse

from recognition_portal import create_app
from recognition_portal.notifications import send_email_test_message, verify_email_delivery_configuration


def main() -> None:
    parser = argparse.ArgumentParser(description="P2P Recognition portal")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=5000)
    parser.add_argument("--debug", action="store_true")
    parser.add_argument(
        "--email-backend-check",
        action="store_true",
        help="Validate the configured email delivery backend and exit.",
    )
    parser.add_argument(
        "--email-test-to",
        help="Send a real email through the configured delivery backend and exit.",
    )
    args = parser.parse_args()

    app = create_app()
    if args.email_backend_check or args.email_test_to:
        if args.email_test_to:
            send_email_test_message(app, args.email_test_to)
            print(f"Email test message sent to {args.email_test_to}.")
        else:
            verify_email_delivery_configuration(app)
            print("Email delivery backend configuration looks valid.")
        return

    app.run(host=args.host, port=args.port, debug=args.debug)


if __name__ == "__main__":
    main()

"""Start the app for local use: python run.py"""
import sys

from app import create_app
from app.config import ConfigError


def main() -> None:
    try:
        app = create_app()
    except ConfigError as exc:
        sys.exit(f"Configuration error: {exc}")
    settings = app.extensions["settings"]
    app.run(host=settings.host, port=settings.port, debug=settings.debug)


if __name__ == "__main__":
    main()

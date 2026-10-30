"""Check launch configuration without connecting to providers or printing secrets."""

import json
import sys

from api import API
from sqlalchemy.exc import SQLAlchemyError

sys.path.insert(0, str(API))


def main() -> int:
    try:
        from app.core.preflight import main as inspect_configuration

        return inspect_configuration()
    except (ValueError, TypeError, SQLAlchemyError):
        # Startup validation may include user-defined URL/credential inputs.
        # Keep even malformed configuration out of release logs.
        print(
            json.dumps(
                {"configuration_ready": False, "issues": ["Settings validation failed"]},
                indent=2,
            )
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

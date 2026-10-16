import argparse
import getpass
import json
import secrets

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.engine import make_url

from app.core.config import PROJECT_ROOT, settings
from app.db.session import get_session_factory
from app.modules.iam.models import Role, User
from app.modules.iam.schemas import UserCreate
from app.modules.iam.security import hasher
from app.modules.iam.service import audit, mutation_lock


def main() -> None:
    parser = argparse.ArgumentParser(description="Create the first IAM administrator.")
    parser.add_argument("--email", required=True)
    parser.add_argument("--name", default="Local Administrator")
    parser.add_argument(
        "--password-file", help="Read the password from a local file instead of a prompt."
    )
    parser.add_argument(
        "--local", action="store_true", help="Generate ignored local-development credentials."
    )
    args = parser.parse_args()
    if args.local and (
        settings.app_env != "development"
        or make_url(settings.database_url).host not in {"127.0.0.1", "localhost"}
    ):
        raise SystemExit(
            "Generated credentials are only available for loopback development databases."
        )
    if args.password_file:
        password = (PROJECT_ROOT / args.password_file).read_text(encoding="utf-8").rstrip("\r\n")
    else:
        password = (
            secrets.token_urlsafe(24)
            if args.local
            else getpass.getpass("New administrator password (12+ characters): ")
        )
    if (
        not args.local
        and not args.password_file
        and password != getpass.getpass("Confirm password: ")
    ):
        raise SystemExit("Passwords do not match.")
    try:
        data = UserCreate(email=args.email, full_name=args.name, password=password)
    except ValidationError:
        raise SystemExit(
            "Provide a valid email, name, and password of 12-128 characters."
        ) from None
    with get_session_factory()() as db:
        mutation_lock(db)
        if db.scalar(select(User.id).limit(1)):
            raise SystemExit("Bootstrap is only allowed before any user accounts exist.")
        role = db.scalar(select(Role).where(Role.code == "ADMIN"))
        if role is None:
            raise SystemExit("Run pnpm api:migrate before bootstrapping.")
        user = User(
            email=str(data.email).lower(),
            full_name=data.full_name,
            password_hash=hasher.hash(password),
            roles=[role],
            primary_role_id=role.id,
        )
        db.add(user)
        db.flush()
        audit(db, "user.created", None, entity_id=user.id)
        audit(db, "role.assigned", None, entity_id=user.id, changes={"role_id": str(role.id)})
        if args.local:
            directory = PROJECT_ROOT / ".local" / "iam"
            directory.mkdir(parents=True, exist_ok=True)
            path = directory / "admin-credentials.json"
            with path.open("x", encoding="utf-8") as credentials:
                credentials.write(json.dumps({"email": user.email, "password": password}, indent=2))
            path.chmod(0o600)
        db.commit()
    print("Initial administrator created.")
    if args.local:
        print(
            "Credentials are in ignored .local/iam/admin-credentials.json. Do not share this file."
        )


if __name__ == "__main__":
    main()

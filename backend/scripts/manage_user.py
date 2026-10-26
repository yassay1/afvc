"""Create / disable / reset fixed accounts. No self-registration.

Usage (from repo root, with .env loaded via dotenv in config):

    python -m backend.scripts.manage_user create <username>
    python -m backend.scripts.manage_user disable <username>
    python -m backend.scripts.manage_user enable <username>
    python -m backend.scripts.manage_user reset-password <username>
"""

from __future__ import annotations

import argparse
import getpass
import sys

from backend.infrastructure.db import init_db
from backend.infrastructure import auth_repo


def _read_password(*, prompt: str = "Password: ", password_stdin: bool = False) -> str:
    if password_stdin:
        password = sys.stdin.readline().rstrip("\r\n")
    else:
        password = getpass.getpass(prompt)
    if not password:
        raise SystemExit("密码不能为空")
    return password


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="AFVC fixed-account admin")
    parser.add_argument(
        "action",
        choices=("create", "disable", "enable", "reset-password"),
        help="create | disable | enable | reset-password",
    )
    parser.add_argument("username", help="account username")
    parser.add_argument(
        "--password-stdin",
        action="store_true",
        help="read password once from stdin (non-interactive bootstrap)",
    )
    args = parser.parse_args(argv)

    init_db(with_checkpointer=False)

    try:
        if args.action == "create":
            if args.password_stdin:
                password = _read_password(password_stdin=True)
            else:
                password = _read_password(prompt="New password: ")
                confirm = _read_password(prompt="Confirm password: ")
                if password != confirm:
                    raise SystemExit("两次密码不一致")
            user = auth_repo.create_user(args.username, password)
            print(f"created user {user.username} (active={user.is_active})")
        elif args.action == "disable":
            user = auth_repo.set_user_active(args.username, active=False)
            print(f"disabled user {user.username}")
        elif args.action == "enable":
            user = auth_repo.set_user_active(args.username, active=True)
            print(f"enabled user {user.username}")
        elif args.action == "reset-password":
            if args.password_stdin:
                password = _read_password(password_stdin=True)
            else:
                password = _read_password(prompt="New password: ")
                confirm = _read_password(prompt="Confirm password: ")
                if password != confirm:
                    raise SystemExit("两次密码不一致")
            user = auth_repo.reset_password(args.username, password)
            print(f"password reset for {user.username}")
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

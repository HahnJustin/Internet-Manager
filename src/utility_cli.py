# utilities/utility_cli.py
from __future__ import annotations

import argparse
import os
import sys

import pyuac

from utilities import tasks
from utilities.server_control import close_server


SERVER_EXE_DEFAULT = "internet_manager_server.exe"
GUI_EXE_DEFAULT = "internet_manager.exe"


def _app_dir() -> str:
    # When frozen, sys.executable is ...\dist\utility.exe
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    # When running from source, utility_cli.py is in ...\src\utilities
    return os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def _require_admin_or_relaunch() -> None:
    if pyuac.isUserAdmin():
        return
    # Relaunches *this* exe/python with same args as admin
    pyuac.runAsAdmin()
    raise SystemExit(0)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="internet_manager_utility")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_install = sub.add_parser("install-tasks", help="Create/update Windows scheduled tasks")
    p_install.add_argument("--server", default=SERVER_EXE_DEFAULT, help="Server exe filename")
    p_install.add_argument("--gui", default=GUI_EXE_DEFAULT, help="GUI exe filename")
    p_install.add_argument("--delay", type=int, default=60, help="GUI delay after logon (seconds)")

    sub.add_parser("remove-tasks", help="Remove Windows scheduled tasks")
    sub.add_parser("close-server", help="Ask the server to shut down")

    args = parser.parse_args(argv)
    base = _app_dir()

    if args.cmd == "install-tasks":
        _require_admin_or_relaunch()
        server_path = os.path.join(base, args.server)
        gui_path = os.path.join(base, args.gui)
        tasks.install_tasks(server_path, gui_path, delay_seconds=args.delay)
        return 0

    if args.cmd == "remove-tasks":
        _require_admin_or_relaunch()
        tasks.uninstall_tasks()
        return 0

    
    if args.cmd == "close-server":
        close_server()
        return 0

    parser.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

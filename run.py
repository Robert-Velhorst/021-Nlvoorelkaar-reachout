#!/usr/bin/env python3
"""Fail-fast launcher for the GUI and operator CLI."""

from __future__ import annotations

import importlib.util
import sys


SUPPORTED_MIN = (3, 10)
SUPPORTED_MAX = (3, 15)
REQUIRED_MODULES = ("bs4", "cryptography", "customtkinter", "requests")


def check_runtime() -> list[str]:
    errors = []
    current = sys.version_info[:2]
    if not SUPPORTED_MIN <= current <= SUPPORTED_MAX:
        errors.append(
            f"Python {SUPPORTED_MIN[0]}.{SUPPORTED_MIN[1]}-"
            f"{SUPPORTED_MAX[0]}.{SUPPORTED_MAX[1]} is required; found {sys.version.split()[0]}"
        )
    missing = [module for module in REQUIRED_MODULES if importlib.util.find_spec(module) is None]
    if missing:
        errors.append(
            "Missing dependencies: " + ", ".join(missing)
            + ". Install with: python -m pip install -r requirements.txt"
        )
    return errors


def main(argv=None) -> int:
    errors = check_runtime()
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 2

    arguments = list(sys.argv[1:] if argv is None else argv)
    if arguments:
        from nlve_cli import main as cli_main

        return cli_main(arguments)

    from main import main as gui_main

    gui_main()
    return 0


if __name__ == "__main__":
    sys.exit(main())

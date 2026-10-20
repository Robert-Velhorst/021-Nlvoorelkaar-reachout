"""Operator CLI for diagnostics, verification, recovery, and data portability."""

from __future__ import annotations

import argparse
import json
import os
import sys

from database.database_manager import DatabaseManager
from services.data_management import DataImporter
from services.diagnostics import ApplicationDoctor, SupportBundleBuilder, verify_local_critical_path
from services.outreach_ledger import OutreachLedger
from services.provider_policy import approval_evidence_sha256, validate_provider_authorization
from utils.backup_manager import BackupManager
from connectors.hai_bridge import sync_feed


def _print(payload) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True, default=str))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="nlve", description="NLvoorelkaar Reachout operator tools")
    subcommands = parser.add_subparsers(dest="command", required=True)
    subcommands.add_parser("doctor", help="Check local readiness without provider network calls")
    subcommands.add_parser("smoke", help="Run the isolated local critical-path smoke test")

    reconcile = subcommands.add_parser("reconcile-sends", help="Fail stale ambiguous send attempts")
    reconcile.add_argument("--minutes", type=int, default=15)

    import_parser = subcommands.add_parser("import-volunteers", help="Import reviewed CSV/JSON candidate data")
    import_parser.add_argument("path")

    export_parser = subcommands.add_parser("export-volunteers", help="Export active volunteer data")
    export_parser.add_argument("path")
    export_parser.add_argument("--format", choices=("json", "csv"), default="json")

    backup_parser = subcommands.add_parser("backup", help="Create and verify a local privacy-filtered backup")
    backup_parser.add_argument("--name", default=None)

    support = subcommands.add_parser("support-bundle", help="Create a privacy-safe diagnostic ZIP")
    support.add_argument("path")

    preflight = subcommands.add_parser(
        "provider-preflight",
        help="Validate a private written NLvoorelkaar approval record without network access",
    )
    preflight.add_argument("path")
    preflight.add_argument(
        "--action",
        action="append",
        choices=("login", "search", "send"),
        default=[],
        help="Required provider action; repeat for multiple actions",
    )

    evidence = subcommands.add_parser(
        "hash-approval-evidence",
        help="Compute the SHA-256 used by a private provider approval record",
    )
    evidence.add_argument("path")

    serve = subcommands.add_parser("serve", help="Run the authenticated web application")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8765)

    hai_sync = subcommands.add_parser("hai-sync", help="Write an authenticated HAI Generic JSON Feed")
    hai_sync.add_argument("output")
    hai_sync.add_argument("--url", default=os.environ.get("NLVE_API_URL", "http://127.0.0.1:8765"))
    hai_sync.add_argument("--limit", type=int, default=100)
    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "doctor":
        result = ApplicationDoctor().run()
        _print(result)
        return 1 if result["status"] == "fail" else 0
    if args.command == "smoke":
        _print(verify_local_critical_path())
        return 0
    if args.command == "support-bundle":
        _print({"path": SupportBundleBuilder().create(args.path)})
        return 0
    if args.command == "provider-preflight":
        result = validate_provider_authorization(
            os.path.abspath(args.path),
            args.action,
        ).public_status()
        _print(result)
        return 0 if result["ready"] else 1
    if args.command == "hash-approval-evidence":
        _print({"sha256": approval_evidence_sha256(os.path.abspath(args.path))})
        return 0
    if args.command == "serve":
        if args.host not in {"127.0.0.1", "localhost", "::1"}:
            raise RuntimeError(
                "Non-loopback binding is disabled. Keep the server on loopback and use the approved Hetzner reverse proxy for public access."
            )
        if not 1 <= args.port <= 65535:
            raise ValueError("port must be between 1 and 65535")
        import uvicorn

        from web_api import create_app

        uvicorn.run(
            create_app(),
            host=args.host,
            port=args.port,
            workers=1,
            access_log=False,
            server_header=False,
        )
        return 0
    if args.command == "hai-sync":
        _print(sync_feed(
            args.url,
            os.environ.get("NLVE_API_TOKEN", ""),
            os.path.abspath(args.output),
            args.limit,
        ))
        return 0

    database = DatabaseManager()
    if args.command == "reconcile-sends":
        count = database.reconcile_ambiguous_send_attempts(args.minutes, actor="cli_operator")
        _print({"reconciled": count, "next_action": "Review provider history before re-approving any failed draft."})
        return 0
    if args.command == "import-volunteers":
        _print(DataImporter(database.db_path).import_volunteers(os.path.abspath(args.path)))
        return 0
    if args.command == "export-volunteers":
        result = OutreachLedger(database).export_volunteer_data(
            os.path.abspath(args.path), args.format, actor="cli_operator"
        )
        _print(result)
        return 0
    if args.command == "backup":
        manager = BackupManager()
        path = manager.create_backup(args.name)
        verified = bool(path and manager.verify_backup(path))
        _print({"path": path, "verified": verified})
        return 0 if verified else 1
    return 2


if __name__ == "__main__":
    sys.exit(main())

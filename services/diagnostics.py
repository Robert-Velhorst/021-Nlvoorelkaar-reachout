"""Local diagnostics, support bundles, and critical-path verification."""

from __future__ import annotations

import json
import os
import platform
import sqlite3
import sys
import tempfile
import zipfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List

from config.runtime import RuntimeSettings
from run import SUPPORTED_MIN, SUPPORTED_MAX
from database.database_manager import DatabaseManager
from google_drive.google_api_services import GoogleDriveManager
from services.outreach_ledger import OutreachLedger
from services.provider_policy import validate_provider_authorization
from utils.backup_manager import BackupManager
from utils.credential_manager import CredentialManager


@dataclass
class DiagnosticCheck:
    name: str
    status: str
    detail: str
    next_action: str = ""


class ApplicationDoctor:
    """Inspect local readiness without contacting external providers."""

    def __init__(self, root: str = ".", database_path: str = "data/nlvoorelkaar.db") -> None:
        self.root = Path(root).resolve()
        self.database_path = (self.root / database_path).resolve()

    def run(self) -> Dict[str, Any]:
        checks: List[DiagnosticCheck] = []
        version = sys.version_info
        supported = SUPPORTED_MIN <= version[:2] <= SUPPORTED_MAX
        checks.append(DiagnosticCheck(
            "python",
            "pass" if supported else "warning",
            platform.python_version(),
            "Use Python 3.15.1; supported compatibility versions are 3.11-3.15." if not supported else "",
        ))

        try:
            settings = RuntimeSettings.from_environment()
            checks.append(DiagnosticCheck("configuration", "pass", json.dumps(settings.public_status(), sort_keys=True)))
        except (TypeError, ValueError) as exc:
            settings = RuntimeSettings()
            checks.append(DiagnosticCheck("configuration", "fail", str(exc), "Correct the NLVE_* environment variables."))

        provider_actions = []
        if settings.live_search_enabled:
            provider_actions.extend(("login", "search"))
        if settings.live_send_enabled:
            provider_actions.extend(("login", "send"))
        provider_authorization = validate_provider_authorization(
            settings.provider_approval_path,
            provider_actions,
        )
        provider_enabled = bool(settings.live_search_enabled or settings.live_send_enabled)
        checks.append(DiagnosticCheck(
            "nlvoorelkaar_authorization",
            "pass" if provider_enabled and provider_authorization.ready else "warning",
            json.dumps(provider_authorization.public_status(), sort_keys=True),
            (
                "Keep live flags disabled and use reviewed imports/manual delivery, or provide a current "
                "private written-approval record."
            ) if not provider_authorization.ready else "",
        ))

        for directory_name in ("data", "backups", "logs"):
            path = self.root / directory_name
            try:
                path.mkdir(mode=0o700, exist_ok=True)
                writable = os.access(path, os.W_OK)
            except OSError:
                writable = False
            checks.append(DiagnosticCheck(
                f"directory:{directory_name}",
                "pass" if writable else "fail",
                "writable" if writable else "not writable",
                f"Grant the current OS user write access to {path}." if not writable else "",
            ))

        try:
            database = DatabaseManager(str(self.database_path))
            health = database.get_database_health()
            checks.append(DiagnosticCheck(
                "database",
                "pass" if health.get("ready") else "fail",
                json.dumps(health, sort_keys=True),
                "Restore a verified backup or inspect foreign-key/integrity failures." if not health.get("ready") else "",
            ))
        except (OSError, RuntimeError, sqlite3.DatabaseError, ValueError) as exc:
            health = {"ready": False, "error_type": type(exc).__name__}
            checks.append(DiagnosticCheck("database", "fail", type(exc).__name__, "Check the data directory and database."))

        credential_manager = CredentialManager(str(self.root / "data"))
        checks.append(DiagnosticCheck(
            "nlvoorelkaar_credentials",
            "pass" if credential_manager.credentials_exist() else "warning",
            "encrypted credentials present" if credential_manager.credentials_exist() else "not configured",
            "Use the first-run setup dialog to store credentials locally." if not credential_manager.credentials_exist() else "",
        ))

        drive_status = GoogleDriveManager().status()
        drive_ready = bool(drive_status.get("client_secret_present"))
        checks.append(DiagnosticCheck(
            "google_drive",
            "pass" if drive_ready else "warning",
            json.dumps(drive_status, sort_keys=True),
            "Provide a private OAuth client file only if Drive backup is needed." if not drive_ready else "",
        ))

        overall = "pass"
        if any(check.status == "fail" for check in checks):
            overall = "fail"
        elif any(check.status == "warning" for check in checks):
            overall = "warning"
        return {
            "status": overall,
            "checks": [asdict(check) for check in checks],
            "external_network_checks_performed": False,
            "runtime": settings.public_status(),
            "database": health,
        }


class SupportBundleBuilder:
    """Create a diagnostic archive that excludes logs, records, and credentials."""

    def __init__(self, root: str = ".") -> None:
        self.root = Path(root).resolve()

    def create(self, output_path: str) -> str:
        destination = Path(output_path).resolve()
        destination.parent.mkdir(parents=True, exist_ok=True)
        doctor = ApplicationDoctor(str(self.root)).run()
        payload = {
            "generated_by": "NLvoorelkaar Reachout support bundle",
            "privacy": "No logs, credentials, tokens, message bodies, or volunteer records are included.",
            "platform": {
                "python": platform.python_version(),
                "system": platform.system(),
                "release": platform.release(),
            },
            "diagnostics": doctor,
        }
        with zipfile.ZipFile(destination, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("diagnostics.json", json.dumps(payload, indent=2, sort_keys=True))
            archive.writestr(
                "README.txt",
                "Privacy-safe support bundle. Review diagnostics.json before sharing.\n",
            )
        return str(destination)


def verify_local_critical_path() -> Dict[str, Any]:
    """Exercise the full local/assisted workflow without network or real credentials."""
    with tempfile.TemporaryDirectory(prefix="nlve-smoke-") as temp_dir:
        root = Path(temp_dir)
        data_dir = root / "data"
        backup_dir = root / "backups"
        export_dir = root / "exports"
        data_dir.mkdir()
        export_dir.mkdir()
        database = DatabaseManager(str(data_dir / "nlvoorelkaar.db"))
        ledger = OutreachLedger(database, RuntimeSettings(environment="test"))

        if not database.add_volunteer({
            "volunteer_id": "smoke-volunteer-1",
            "name": "Smoke Test Volunteer",
            "location": "Arnhem",
            "categories": "maatjes",
            "skills": "luisteren",
            "profile_url": "https://www.nlvoorelkaar.nl/",
        }):
            raise RuntimeError("Could not create smoke-test candidate")

        campaign_id = database.add_campaign({
            "name": "Smoke Test Campaign",
            "description": "Local verification only",
            "target_categories": "maatjes",
            "target_location": "Arnhem",
            "target_distance": 10,
            "message_template": "Beste {name}, dit is een lokaal gecontroleerd bericht voor {location}.",
        })
        readiness = ledger.check_campaign_readiness(campaign_id)
        if not readiness.get("ready"):
            raise RuntimeError(f"Smoke campaign not ready: {readiness.get('issues')}")

        draft_id = ledger.create_message_drafts(campaign_id)[0]
        ledger.approve_message(draft_id, "Local smoke-test approval", actor="smoke_test")
        attempt_id = ledger.confirm_manual_send(
            draft_id,
            "local_smoke_test_no_external_send",
            actor="smoke_test",
        )
        response_id = ledger.record_response(
            "smoke-volunteer-1",
            campaign_id,
            "Wilt u mij meer informatie sturen?",
            source="local_smoke_test",
        )
        follow_ups = ledger.get_follow_up_queue()
        if not follow_ups:
            raise RuntimeError("Smoke-test response did not create a follow-up")
        ledger.approve_follow_up(follow_ups[0]["id"], actor="smoke_test")
        ledger.confirm_follow_up_sent(
            follow_ups[0]["id"],
            "local_smoke_test_no_external_send",
            actor="smoke_test",
        )
        ledger.record_outreach_outcome(
            "smoke-volunteer-1",
            campaign_id,
            "interested",
            response_id=response_id,
            follow_up_id=follow_ups[0]["id"],
            actor="smoke_test",
        )

        export_path = export_dir / "volunteers.json"
        export_result = ledger.export_volunteer_data(str(export_path), "json", actor="smoke_test")
        backup_manager = BackupManager(str(data_dir), str(backup_dir))
        backup_path = backup_manager.create_backup("critical_path_smoke")
        backup_verified = bool(backup_path and backup_manager.verify_backup(backup_path))
        if not backup_verified:
            raise RuntimeError("Smoke-test backup verification failed")

        return {
            "status": "pass",
            "network_used": False,
            "external_messages_sent": 0,
            "campaign_id": campaign_id,
            "draft_id": draft_id,
            "manual_send_attempt_id": attempt_id,
            "response_id": response_id,
            "follow_up_id": follow_ups[0]["id"],
            "export_record_count": export_result["record_count"],
            "backup_verified": backup_verified,
            "database_ready": database.get_database_health()["ready"],
        }

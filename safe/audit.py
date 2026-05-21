import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass
class Auditor:
    path: str = "audit.log"

    def _append(self, record: dict) -> None:
        record["ts"] = datetime.now(timezone.utc).isoformat()
        with open(self.path, "a") as f:
            f.write(json.dumps(record) + "\n")

    def log_startup(self, dry_run: bool) -> None:
        self._append({"event": "startup", "dry_run": dry_run})

    def log_intent(self, signal_id: str, side: str, size_pct: float, dry_run: bool) -> None:
        self._append({"event": "intent", "signal_id": signal_id, "side": side, "size_pct": size_pct, "dry_run": dry_run})

    def log_result(self, signal_id: str, status: str, detail: str = "") -> None:
        # status: "ok" | "dry_run" | "error"
        self._append({"event": "result", "signal_id": signal_id, "status": status, "detail": detail})

    def log_guardrail_block(self, reason: str, detail: str = "") -> None:
        self._append({"event": "guardrail_block", "reason": reason, "detail": detail})

    def log_tripwire(self, matched: str) -> None:
        self._append({"event": "tripwire", "matched": matched})

    def log_error(self, detail: str) -> None:
        self._append({"event": "error", "detail": detail})

    def reconcile(self) -> list[str]:
        """Return signal_ids that have an intent entry but no result (orphaned by a prior crash)."""
        if not os.path.exists(self.path):
            return []
        intents: set[str] = set()
        results: set[str] = set()
        with open(self.path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue
                event = record.get("event")
                sid = record.get("signal_id")
                if event == "intent" and sid:
                    intents.add(sid)
                elif event == "result" and sid:
                    results.add(sid)
        return sorted(intents - results)

#!/usr/bin/env python3
"""Rejeu ciblé, reprenable, des candidats du manifeste local.

Chaque PDF est extrait par le harnais d'audit dans un processus séparé.
Un résultat déjà présent sous le parseur cible est conservé. Le script ne
modifie ni l'ancien journal 480 ni le dataset publié.
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
APP_ROOT = ROOT.parent.parent
MANIFEST = ROOT / "manifest.json"
STATUS = ROOT / "replay_status.jsonl"
COMPANIES = APP_ROOT / "audits" / "audit_bpa_480_2016_2025_2026-10-25" / "companies_minimal.json"
TARGET_PARSER = "eps-evidence-v2.1.1"
PER_DOCUMENT_TIMEOUT = 300


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def append_status(payload: dict) -> None:
    with STATUS.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(payload, ensure_ascii=False) + "\n")
        stream.flush()


def already_done(path: Path) -> bool:
    if not path.exists():
        return False
    try:
        result = load_json(path)
    except Exception:
        return False
    parser = (
        ((result.get("extraction") or {}).get("per_share_observations") or {}).get(
            "parser_version"
        )
    )
    return parser == TARGET_PARSER


def main() -> int:
    manifest = load_json(MANIFEST)
    documents = manifest.get("documents") or []
    todo = [item for item in documents if item.get("replay_status") == "A_REJOUER"]
    print(f"Rejeu ciblé : {len(todo)} documents", flush=True)
    failures = 0
    for index, item in enumerate(todo, 1):
        candidate = ROOT / str(item["candidate_file"])
        output = ROOT / str(item["result_file"])
        label = item.get("label") or item.get("candidate_id")
        if already_done(output):
            print(f"[{index}/{len(todo)}] déjà fait : {item['ticker']} {label}", flush=True)
            continue
        started = time.time()
        print(f"[{index}/{len(todo)}] extraction : {item['ticker']} {label}", flush=True)
        command = [
            sys.executable,
            "-B",
            str(APP_ROOT / "ingestion" / "audit_bpa_480.py"),
            "--phase",
            "extract-one",
            "--candidate-file",
            str(candidate),
            "--companies-file",
            str(COMPANIES),
            "--extract-output-file",
            str(output),
            "--no-ocr",
        ]
        try:
            completed = subprocess.run(
                command,
                cwd=APP_ROOT,
                text=True,
                capture_output=True,
                timeout=PER_DOCUMENT_TIMEOUT,
                check=False,
            )
            status = "OK" if completed.returncode == 0 and already_done(output) else "ECHEC"
            error = (completed.stderr or completed.stdout or "")[-1000:] if status != "OK" else ""
            returncode = completed.returncode
        except subprocess.TimeoutExpired as exc:
            status = "TIMEOUT"
            error = f"timeout après {PER_DOCUMENT_TIMEOUT}s"
            returncode = None
            if output.exists():
                output.unlink()
        elapsed = round(time.time() - started, 3)
        if status != "OK":
            failures += 1
        append_status(
            {
                "candidate_id": item["candidate_id"],
                "ticker": item["ticker"],
                "label": label,
                "status": status,
                "returncode": returncode,
                "seconds": elapsed,
                "error_tail": error,
            }
        )
        print(f"    -> {status} en {elapsed}s", flush=True)
    print(f"Terminé ; échecs/timeouts : {failures}", flush=True)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())

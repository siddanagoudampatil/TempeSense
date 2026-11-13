"""Shared constants for the evaluation harness."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from date_windows import AZ_TZ

EVAL_DIR = Path(__file__).resolve().parent
REPO_ROOT = EVAL_DIR.parent
QUESTIONS_PATH = EVAL_DIR / "questions.json"
GOLD_PATH = EVAL_DIR / "gold.json"
RESULTS_DIR = EVAL_DIR / "results"

# Relative phrases in questions ("yesterday", "this weekend") are resolved against this
# fixed moment so that gold answers stay valid. It is a Friday in Arizona time (UTC-7).
FIXED_NOW = datetime(2026, 11, 13, 12, 0, tzinfo=AZ_TZ)

# Tool metadata the harness needs. The record-id field is what an answer would cite.
TOOLS = {
    "query_tempe_general_offenses": {"id_field": "PrimaryKey", "short": "offenses"},
    "query_tempe_street_closures": {"id_field": "PermitNumber", "short": "closures"},
}

RESULT_CAP = 50          # the agent's per-query record cap
GOLD_MAX_RECORDS = 2000  # safety stop when paging gold queries

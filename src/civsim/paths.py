"""Resolve data paths for local dev and AWS Lambda (/var/task)."""

from __future__ import annotations

import os
from pathlib import Path


def project_root() -> Path:
    if task_root := os.environ.get("LAMBDA_TASK_ROOT"):
        return Path(task_root)
    return Path(__file__).resolve().parent.parent.parent


def resolve_data_path(env_key: str, default_relative: str) -> Path:
    raw = os.environ.get(env_key, default_relative)
    path = Path(raw)
    if path.is_absolute():
        return path
    return project_root() / path

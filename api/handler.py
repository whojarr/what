"""AWS Lambda entrypoint for FastAPI (API Gateway HTTP API /api/*)."""

from __future__ import annotations

import sys
from pathlib import Path

_root = Path(__file__).resolve().parent.parent
_src = _root / "src"
for p in (_src, _root):
    s = str(p)
    if s not in sys.path:
        sys.path.insert(0, s)

from mangum import Mangum  # noqa: E402

from api.main import app  # noqa: E402

handler = Mangum(app, api_gateway_base_path="/api", lifespan="off")

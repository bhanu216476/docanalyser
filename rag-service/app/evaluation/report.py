from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.evaluation.models import EvaluationReport


def export_evaluation_report(report: EvaluationReport, output_path: str | Path) -> str:
    """Export the report as JSON for downstream analysis or CI artifacts."""
    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = report.model_dump(mode="json")
    target.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return str(target)


__all__ = ["EvaluationReport", "export_evaluation_report"]

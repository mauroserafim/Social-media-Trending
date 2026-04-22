import json
import logging
from datetime import datetime
from pathlib import Path

from src.models.trend import TrendIdea

logger = logging.getLogger(__name__)


class JSONExporter:
    def __init__(self, output_dir: str = "outputs/json"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def export(self, ideas: list[TrendIdea], run_id: str = "") -> str:
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        filename = f"trends_{timestamp}.json"
        if run_id:
            filename = f"trends_{run_id}_{timestamp}.json"

        payload = {
            "generated_at": datetime.utcnow().isoformat(),
            "run_id": run_id,
            "total": len(ideas),
            "ideas": [idea.to_dict() for idea in ideas],
        }

        filepath = self.output_dir / filename
        filepath.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

        # Always overwrite latest.json for easy access
        latest = self.output_dir / "latest.json"
        latest.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

        logger.info(f"JSON exported to: {filepath}")
        return str(filepath)

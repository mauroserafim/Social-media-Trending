import json
import logging
from pathlib import Path

from src.models.trend import TrendReport

logger = logging.getLogger(__name__)


def _section_to_dict(section) -> dict:
    return {
        "platform": section.platform,
        "region": section.region,
        "label": section.label,
        "trends": [
            {
                "title": t.title,
                "source": t.source,
                "url": t.url,
                "score": t.raw_score,
                "region": t.region,
                "views": t.views,
            }
            for t in section.trends
        ],
    }


class JSONExporter:
    def __init__(self, output_dir: str = "outputs/json"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def export(self, report: TrendReport) -> str:
        payload = {
            "generated_at": report.generated_at.isoformat(),
            "run_id": report.run_id,
            "summary": {
                "total_br": sum(len(s.trends) for s in report.sections_br),
                "total_us": sum(len(s.trends) for s in report.sections_us),
                "cross_platform_topics": len(report.cross_platform),
                "niche_ideas": len(report.niche_ideas),
            },
            "sections_br": [_section_to_dict(s) for s in report.sections_br],
            "sections_us": [_section_to_dict(s) for s in report.sections_us],
            "cross_platform": [
                {
                    "topic": cp.topic,
                    "platforms": cp.platforms,
                    "count": cp.count,
                    "score": cp.score,
                    "sample_titles": cp.sample_titles,
                }
                for cp in report.cross_platform
            ],
            "niche_ideas": [idea.to_dict() for idea in report.niche_ideas],
        }

        timestamp = report.generated_at.strftime("%Y%m%d_%H%M%S")
        filename = f"trends_{report.run_id}_{timestamp}.json"
        filepath = self.output_dir / filename
        filepath.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

        latest = self.output_dir / "latest.json"
        latest.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

        logger.info(f"JSON exported: {filepath}")
        return str(filepath)

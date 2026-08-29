import json
import logging
from pathlib import Path

from src.models.carousel import CarouselPost

logger = logging.getLogger(__name__)


class CarouselJSONExporter:
    def __init__(self, output_dir: str = "outputs/carousel"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def export(self, post: CarouselPost) -> str:
        payload = post.to_dict()

        timestamp = post.generated_at.strftime("%Y%m%d_%H%M%S")
        filename = f"carousel_{post.topic_slug}_{timestamp}.json"
        filepath = self.output_dir / filename
        filepath.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

        latest = self.output_dir / "latest.json"
        latest.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

        logger.info(f"Carousel JSON exported: {filepath}")
        return str(filepath)

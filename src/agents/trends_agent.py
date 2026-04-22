import logging
import os
import uuid
from datetime import datetime

from src.analyzers.ai_analyzer import AIAnalyzer
from src.collectors.google_trends_collector import GoogleTrendsCollector
from src.collectors.rss_collector import RSSCollector
from src.collectors.youtube_collector import YouTubeCollector
from src.exporters.json_exporter import JSONExporter
from src.exporters.markdown_exporter import MarkdownExporter
from src.models.trend import RawTrend, TrendIdea
from src.storage.database import Database

logger = logging.getLogger(__name__)


class TrendsAgent:
    def __init__(self):
        self.run_id = os.getenv("GITHUB_RUN_ID", str(uuid.uuid4())[:8])
        self.youtube = YouTubeCollector()
        self.rss = RSSCollector()
        self.analyzer = AIAnalyzer()
        self.db = Database()
        self.json_exp = JSONExporter()
        self.md_exp = MarkdownExporter()

    def _collect_all(self) -> list[RawTrend]:
        raw: list[RawTrend] = []

        logger.info("--- Phase 1: Data Collection ---")

        try:
            raw.extend(self.youtube.collect())
        except Exception as e:
            logger.error(f"YouTube collection failed: {e}")

        try:
            raw.extend(self.rss.collect())
        except Exception as e:
            logger.error(f"RSS collection failed: {e}")

        try:
            gt_collector = GoogleTrendsCollector()
            raw.extend(gt_collector.collect())
        except Exception as e:
            logger.error(f"Google Trends collection failed: {e}")

        logger.info(f"Total raw trends collected: {len(raw)}")
        return raw

    def _deduplicate(self, trends: list[RawTrend]) -> list[RawTrend]:
        seen: set[str] = set()
        unique: list[RawTrend] = []
        for t in trends:
            key = t.title.lower().strip()[:60]
            if key not in seen:
                seen.add(key)
                unique.append(t)
        logger.info(f"After deduplication: {len(unique)} trends")
        return unique

    def run(self, max_ideas: int = 10) -> list[TrendIdea]:
        start = datetime.utcnow()
        logger.info(f"=== AI Trends Agent started | run_id={self.run_id} ===")

        raw = self._collect_all()
        raw = self._deduplicate(raw)

        if raw:
            self.db.save_raw_trends(raw)

        logger.info("--- Phase 2: AI Analysis ---")
        ideas = self.analyzer.analyze(raw, max_ideas=max_ideas)

        if ideas:
            self.db.save_trend_ideas(ideas, run_id=self.run_id)
            json_path = self.json_exp.export(ideas, run_id=self.run_id)
            md_path = self.md_exp.export(ideas, run_id=self.run_id)
            logger.info(f"Exported: {json_path}, {md_path}")

        elapsed = (datetime.utcnow() - start).total_seconds()
        logger.info(f"=== Done in {elapsed:.1f}s | {len(ideas)} ideas generated ===")
        return ideas

    def close(self):
        self.youtube.close()
        self.rss.close()
        self.db.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

import logging
import os
import re
import uuid
from collections import defaultdict
from datetime import datetime

from src.analyzers.ai_analyzer import AIAnalyzer
from src.collectors.google_trends_collector import GoogleTrendsCollector
from src.collectors.reddit_collector import RedditCollector
from src.collectors.rss_collector import RSSCollector
from src.collectors.tiktok_collector import TikTokCollector
from src.collectors.youtube_collector import YouTubeCollector
from src.exporters.email_notifier import EmailNotifier
from src.exporters.json_exporter import JSONExporter
from src.exporters.markdown_exporter import MarkdownExporter
from src.models.trend import CrossPlatformTrend, RawTrend, TrendReport, TrendSection
from src.storage.database import Database

logger = logging.getLogger(__name__)

PLATFORM_META: dict[str, tuple[str, str]] = {
    "youtube":       ("📺", "YouTube"),
    "rss":           ("📰", "Notícias"),
    "google_trends": ("📊", "Google Trends"),
    "reddit":        ("💬", "Fóruns (Reddit)"),
    "tiktok":        ("🎵", "TikTok"),
}

STOPWORDS = {
    # English
    "the", "and", "for", "that", "this", "with", "from", "are", "was",
    "were", "have", "been", "will", "about", "after", "over", "under",
    "into", "what", "when", "where", "which", "there", "their", "they",
    "more", "than", "your", "just", "like", "some", "would", "could",
    # Portuguese
    "que", "para", "como", "uma", "mais", "isso", "este", "esta",
    "este", "pelo", "pela", "nos", "nas", "dos", "das", "com", "por",
    "seu", "sua", "seus", "suas", "mas", "não", "ele", "ela", "ser",
    "foi", "tem", "são", "está", "isso", "aqui", "todo", "toda",
}


class TrendsAgent:
    def __init__(self):
        self.run_id = os.getenv("GITHUB_RUN_ID", str(uuid.uuid4())[:8])
        self.youtube = YouTubeCollector()
        self.rss = RSSCollector()
        self.reddit = RedditCollector()
        self.tiktok = TikTokCollector()
        self.analyzer = AIAnalyzer()
        self.db = Database()
        self.json_exp = JSONExporter()
        self.md_exp = MarkdownExporter()
        self.email = EmailNotifier()

    def _collect_all(self) -> list[RawTrend]:
        raw: list[RawTrend] = []
        logger.info("--- Phase 1: Data Collection (no filters) ---")

        collectors = [
            ("YouTube",       lambda: self.youtube.collect()),
            ("RSS/Jornais",   lambda: self.rss.collect()),
            ("Reddit",        lambda: self.reddit.collect()),
            ("TikTok",        lambda: self.tiktok.collect()),
            ("Google Trends", lambda: GoogleTrendsCollector().collect()),
        ]

        for name, fn in collectors:
            try:
                result = fn()
                raw.extend(result)
                logger.info(f"{name}: {len(result)} trends collected")
            except Exception as e:
                logger.error(f"{name} collection failed: {e}")

        logger.info(f"Total raw trends: {len(raw)}")
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

    def _build_sections(
        self, trends: list[RawTrend]
    ) -> tuple[list[TrendSection], list[TrendSection]]:
        by_platform_region: dict[tuple[str, str], list[RawTrend]] = defaultdict(list)

        for t in trends:
            platform = t.source.split(":")[0]
            region = t.region or "GLOBAL"
            by_platform_region[(platform, region)].append(t)

        sections_br: list[TrendSection] = []
        sections_us: list[TrendSection] = []

        for platform in PLATFORM_META:
            emoji, label = PLATFORM_META[platform]
            for region, target in [("BR", sections_br), ("US", sections_us)]:
                items = by_platform_region.get((platform, region), [])
                if items:
                    top10 = sorted(items, key=lambda x: x.raw_score, reverse=True)[:10]
                    target.append(TrendSection(
                        platform=platform,
                        region=region,
                        label=f"{label} ({region})",
                        emoji=emoji,
                        trends=top10,
                    ))

        return sections_br, sections_us

    def _extract_keywords(self, title: str) -> set[str]:
        text = re.sub(r"[^\w\s]", " ", title.lower())
        words = text.split()
        single = {w for w in words if len(w) > 4 and w not in STOPWORDS}

        # Bigrams for more specific matching
        bigrams = set()
        clean = [w for w in words if len(w) > 3 and w not in STOPWORDS]
        for i in range(len(clean) - 1):
            bigrams.add(f"{clean[i]} {clean[i+1]}")

        return single | bigrams

    def _find_br_us_connections(self, trends: list[RawTrend]) -> list[CrossPlatformTrend]:
        """Find topics that appear in BOTH BR and US sources — like a Brazilian case covered in US news."""
        br_trends = [t for t in trends if t.region == "BR"]
        us_trends = [t for t in trends if t.region == "US"]

        br_kw: dict[str, list[RawTrend]] = defaultdict(list)
        us_kw: dict[str, list[RawTrend]] = defaultdict(list)

        for t in br_trends:
            for kw in self._extract_keywords(t.title):
                br_kw[kw].append(t)
        for t in us_trends:
            for kw in self._extract_keywords(t.title):
                us_kw[kw].append(t)

        common = set(br_kw.keys()) & set(us_kw.keys())
        connections: list[CrossPlatformTrend] = []
        seen: set[str] = set()

        for kw in sorted(common, key=lambda k: len(br_kw[k]) + len(us_kw[k]), reverse=True):
            if kw in seen:
                continue
            seen.add(kw)
            related = br_kw[kw][:3] + us_kw[kw][:3]
            avg_score = sum(t.raw_score for t in related) / len(related)
            sample_titles = list(dict.fromkeys(t.title for t in related))[:5]
            connections.append(CrossPlatformTrend(
                topic=kw,
                platforms=["BR", "US"],
                count=len(br_kw[kw]) + len(us_kw[kw]),
                score=round(avg_score, 2),
                sample_titles=sample_titles,
            ))

        connections.sort(key=lambda x: (x.count, x.score), reverse=True)
        return connections[:10]

    def _find_cross_platform(self, trends: list[RawTrend]) -> list[CrossPlatformTrend]:
        keyword_map: dict[str, dict[str, list[RawTrend]]] = defaultdict(
            lambda: defaultdict(list)
        )

        for t in trends:
            platform = t.source.split(":")[0]
            for kw in self._extract_keywords(t.title):
                keyword_map[kw][platform].append(t)

        cross: list[CrossPlatformTrend] = []
        seen: set[str] = set()

        for kw, platform_dict in sorted(
            keyword_map.items(), key=lambda x: len(x[1]), reverse=True
        ):
            if len(platform_dict) < 2 or kw in seen:
                continue
            seen.add(kw)
            all_related = [t for ts in platform_dict.values() for t in ts]
            avg_score = sum(t.raw_score for t in all_related) / len(all_related)
            sample_titles = list(dict.fromkeys(t.title for t in all_related))[:5]
            cross.append(CrossPlatformTrend(
                topic=kw,
                platforms=list(platform_dict.keys()),
                count=len(platform_dict),
                score=round(avg_score, 2),
                sample_titles=sample_titles,
            ))

        cross.sort(key=lambda x: (x.count, x.score), reverse=True)
        return cross[:15]

    def run(self, max_ideas: int = 10) -> TrendReport:
        start = datetime.utcnow()
        logger.info(f"=== Trends Agent started | run_id={self.run_id} ===")

        raw = self._collect_all()
        raw = self._deduplicate(raw)

        if raw:
            self.db.save_raw_trends(raw)

        sections_br, sections_us = self._build_sections(raw)
        cross_platform = self._find_cross_platform(raw)
        br_us_connections = self._find_br_us_connections(raw)

        logger.info(
            f"Cross-platform: {len(cross_platform)} topics | "
            f"BR+US connections: {len(br_us_connections)}"
        )

        logger.info("--- Phase 2: AI Niche Analysis ---")
        niche_ideas = self.analyzer.analyze_niche(raw, cross_platform, max_ideas=max_ideas)

        if niche_ideas:
            self.db.save_niche_ideas(niche_ideas, run_id=self.run_id)

        report = TrendReport(
            run_id=self.run_id,
            sections_br=sections_br,
            sections_us=sections_us,
            cross_platform=cross_platform,
            br_us_connections=br_us_connections,
            niche_ideas=niche_ideas,
        )

        json_path = self.json_exp.export(report)
        md_path = self.md_exp.export(report)
        logger.info(f"Exported: {json_path}, {md_path}")
        self.email.send(report)

        elapsed = (datetime.utcnow() - start).total_seconds()
        logger.info(
            f"=== Done in {elapsed:.1f}s | {len(niche_ideas)} niche ideas | "
            f"{len(raw)} raw trends ==="
        )
        return report

    def close(self):
        self.youtube.close()
        self.rss.close()
        self.reddit.close()
        self.tiktok.close()
        self.db.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

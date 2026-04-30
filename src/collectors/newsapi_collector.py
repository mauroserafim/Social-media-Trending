import logging
import os
from datetime import datetime, timezone

import httpx

from src.models.trend import RawTrend

logger = logging.getLogger(__name__)

NEWSAPI_BASE = "https://newsapi.org/v2"

QUERIES = {
    "BR": [
        "Brasil economia",
        "imigração EUA brasileiros",
        "dólar real câmbio",
        "custo de vida",
        "visto americano",
    ],
    "US": [
        "immigration United States",
        "cost of living USA",
        "inflation economy",
        "job market salary",
        "deportation policy",
    ],
}

LANGUAGE = {"BR": "pt", "US": "en"}


class NewsAPICollector:
    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.getenv("NEWSAPI_KEY", "")
        self.client = httpx.Client(timeout=20)

    def _fetch(self, query: str, language: str) -> list[dict]:
        if not self.api_key:
            return []
        try:
            r = self.client.get(
                f"{NEWSAPI_BASE}/everything",
                params={
                    "q": query,
                    "language": language,
                    "sortBy": "publishedAt",
                    "pageSize": 5,
                    "apiKey": self.api_key,
                },
            )
            r.raise_for_status()
            return r.json().get("articles", [])
        except Exception as e:
            logger.warning(f"NewsAPI fetch failed [{query}]: {e}")
            return []

    def _parse_date(self, raw: str | None) -> datetime | None:
        if not raw:
            return None
        try:
            return datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except Exception:
            return None

    def _score(self, published_at: datetime | None) -> float:
        if not published_at:
            return 30.0
        hours_old = (datetime.now(timezone.utc) - published_at).total_seconds() / 3600
        if hours_old < 1:
            return 100.0
        if hours_old < 6:
            return 80.0
        if hours_old < 24:
            return 60.0
        if hours_old < 72:
            return 40.0
        return 20.0

    def collect(self) -> list[RawTrend]:
        if not self.api_key:
            logger.warning("NEWSAPI_KEY not set — skipping news collection")
            return []

        trends: list[RawTrend] = []
        for region, queries in QUERIES.items():
            lang = LANGUAGE[region]
            for query in queries:
                articles = self._fetch(query, lang)
                for article in articles:
                    pub_at = self._parse_date(article.get("publishedAt"))
                    source_name = article.get("source", {}).get("name", "NewsAPI")
                    trends.append(RawTrend(
                        title=article.get("title", "").strip(),
                        source=f"news:{source_name}",
                        url=article.get("url", ""),
                        published_at=pub_at,
                        region=region,
                        keywords=[],
                        raw_score=self._score(pub_at),
                    ))

        # Deduplicate by title
        seen: set[str] = set()
        unique: list[RawTrend] = []
        for t in trends:
            key = t.title.lower()[:60]
            if key not in seen and t.title:
                seen.add(key)
                unique.append(t)

        logger.info(f"NewsAPI: collected {len(unique)} articles")
        return unique

    def close(self):
        self.client.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

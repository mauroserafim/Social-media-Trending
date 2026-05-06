import logging
import time

import feedparser
import httpx

from src.models.trend import RawTrend

logger = logging.getLogger(__name__)

# Google Trends daily RSS — works on cloud servers without IP blocks
REGIONS = {
    "BR": "BR",
    "US": "US",
}

TRENDS_RSS_URL = "https://trends.google.com/trends/trendingsearches/daily/rss?geo={geo}"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
}


class GoogleTrendsCollector:
    def _fetch_trending(self, geo: str, limit: int = 20) -> list[str]:
        url = TRENDS_RSS_URL.format(geo=geo)
        try:
            # feedparser accepts a URL directly but doesn't set a User-Agent header,
            # so fetch raw bytes first and let feedparser parse the content.
            r = httpx.get(url, headers=HEADERS, timeout=20, follow_redirects=True)
            r.raise_for_status()
            feed = feedparser.parse(r.content)
            titles = [entry.title for entry in feed.entries if entry.get("title")]
            logger.info(f"Google Trends RSS ({geo}): {len(titles)} raw entries")
            return titles[:limit]
        except Exception as e:
            logger.error(f"Google Trends RSS error for {geo}: {e}")
            return []

    def collect(self) -> list[RawTrend]:
        trends: list[RawTrend] = []

        for region_code, geo in REGIONS.items():
            logger.info(f"Google Trends (RSS) for {region_code}")
            keywords = self._fetch_trending(geo, limit=20)
            for i, kw in enumerate(keywords):
                score = max(20.0 - i, 5.0)
                trends.append(RawTrend(
                    title=kw,
                    source="google_trends",
                    url=f"https://trends.google.com/trends/explore?q={kw}&geo={region_code}",
                    region=region_code,
                    keywords=[kw],
                    raw_score=score,
                ))
            time.sleep(1.0)

        logger.info(f"Google Trends: collected {len(trends)} trends")
        return trends

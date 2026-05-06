import logging
import time
from datetime import datetime, timedelta, timezone

import httpx

from src.models.trend import RawTrend

logger = logging.getLogger(__name__)

# Wikipedia pageviews API — free, no key, no cloud IP block.
# Shows top-viewed articles for the previous day (Google Trends blocked all cloud IPs).
REGIONS = {
    "BR": "pt.wikipedia.org",
    "US": "en.wikipedia.org",
}

WIKI_API = (
    "https://wikimedia.org/api/rest_v1/metrics/pageviews/top"
    "/{project}/all-access/{year}/{month:02d}/{day:02d}"
)

# Articles that are always in the top views but have no content value
SKIP_TITLES = {
    "Main_Page", "Wikipédia:Página_principal", "Special:Search",
    "Wikpédia:Esplanada", "-", "Wikipedia:Featured_pictures",
}

HEADERS = {"User-Agent": "TrendsBot/2.0 (social-media-trending; research)"}


class GoogleTrendsCollector:
    def _fetch_trending(self, geo: str, project: str, limit: int = 20) -> list[tuple[str, int]]:
        yesterday = datetime.now(timezone.utc) - timedelta(days=1)
        url = WIKI_API.format(
            project=project,
            year=yesterday.year,
            month=yesterday.month,
            day=yesterday.day,
        )
        try:
            r = httpx.get(url, headers=HEADERS, timeout=15, follow_redirects=True)
            r.raise_for_status()
            articles = r.json()["items"][0]["articles"]
            results = []
            for a in articles:
                title = a["article"].replace("_", " ")
                if title in SKIP_TITLES or title.startswith("Special:"):
                    continue
                results.append((title, a["views"]))
                if len(results) >= limit:
                    break
            logger.info(f"Wikipedia trending ({geo}): {len(results)} articles")
            return results
        except Exception as e:
            logger.error(f"Wikipedia trending error for {geo}: {e}")
            return []

    def collect(self) -> list[RawTrend]:
        trends: list[RawTrend] = []

        for region_code, project in REGIONS.items():
            logger.info(f"Wikipedia Trending for {region_code} ({project})")
            articles = self._fetch_trending(region_code, project, limit=20)
            for i, (title, views) in enumerate(articles):
                score = max(20.0 - i, 5.0)
                lang = "pt" if region_code == "BR" else "en"
                slug = title.replace(" ", "_")
                trends.append(RawTrend(
                    title=title,
                    source="google_trends",
                    url=f"https://{lang}.wikipedia.org/wiki/{slug}",
                    region=region_code,
                    keywords=[title],
                    raw_score=score,
                ))
            time.sleep(0.5)

        logger.info(f"Wikipedia Trending: collected {len(trends)} trends")
        return trends

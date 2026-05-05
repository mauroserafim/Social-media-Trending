import logging
import time

from src.models.trend import RawTrend

logger = logging.getLogger(__name__)

# trending_searches() uses a different endpoint that works on cloud servers.
# build_payload() + interest_over_time() is blocked by Google on AWS/Azure/GCP IPs.
REGIONS = {
    "BR": "brazil",
    "US": "united_states",
}


class GoogleTrendsCollector:
    def __init__(self):
        self._client = None

    def _get_client(self):
        if self._client is None:
            try:
                from pytrends.request import TrendReq
                self._client = TrendReq(hl="pt-BR", tz=360, timeout=(10, 25))
            except ImportError:
                logger.error("pytrends not installed. Run: pip install pytrends")
                raise
        return self._client

    def _fetch_trending(self, geo: str, limit: int = 20) -> list[str]:
        try:
            pt = self._get_client()
            df = pt.trending_searches(pn=geo)
            return df[0].tolist()[:limit]
        except Exception as e:
            logger.error(f"Google Trends trending error for {geo}: {e}")
            return []

    def collect(self) -> list[RawTrend]:
        trends: list[RawTrend] = []

        for region_code, geo_name in REGIONS.items():
            logger.info(f"Google Trends (trending searches) for {region_code}")
            keywords = self._fetch_trending(geo_name, limit=20)
            for i, kw in enumerate(keywords):
                # Top results get higher score
                score = max(20.0 - i, 5.0)
                trends.append(RawTrend(
                    title=kw,
                    source="google_trends",
                    url=f"https://trends.google.com/trends/explore?q={kw}&geo={region_code}",
                    region=region_code,
                    keywords=[kw],
                    raw_score=score,
                ))
            time.sleep(2.0)

        logger.info(f"Google Trends: collected {len(trends)} trends")
        return trends

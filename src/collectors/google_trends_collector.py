import logging
import time
from typing import Optional

from src.models.trend import RawTrend

logger = logging.getLogger(__name__)

REGIONS = {
    "BR": "brazil",
    "US": "united_states",
}

NICHES = [
    "inteligência artificial",
    "artificial intelligence",
    "finanças pessoais",
    "personal finance",
    "saúde",
    "health",
    "tecnologia",
    "technology",
    "entretenimento",
    "entertainment",
]


class GoogleTrendsCollector:
    def __init__(self):
        self._client = None

    def _get_client(self):
        if self._client is None:
            try:
                from pytrends.request import TrendReq
                self._client = TrendReq(hl="pt-BR", tz=360)
            except ImportError:
                logger.error("pytrends not installed. Run: pip install pytrends")
                raise
        return self._client

    def _fetch_trending(self, geo: str) -> list[dict]:
        try:
            pt = self._get_client()
            df = pt.trending_searches(pn=geo)
            return df[0].tolist()
        except Exception as e:
            logger.error(f"Google Trends error for geo {geo}: {e}")
            return []

    def _fetch_interest(self, keyword: str, geo: str) -> float:
        try:
            pt = self._get_client()
            pt.build_payload([keyword], cat=0, timeframe="now 1-d", geo=geo)
            data = pt.interest_over_time()
            if data.empty:
                return 0.0
            return float(data[keyword].mean())
        except Exception as e:
            logger.warning(f"Interest fetch failed for '{keyword}': {e}")
            return 0.0

    def collect(self) -> list[RawTrend]:
        trends: list[RawTrend] = []

        for region_code, geo_name in REGIONS.items():
            logger.info(f"Collecting Google Trends for: {region_code}")
            keywords = self._fetch_trending(geo_name)
            time.sleep(1)

            for kw in keywords[:15]:
                score = self._fetch_interest(kw, region_code)
                time.sleep(0.5)
                trends.append(
                    RawTrend(
                        title=kw,
                        source="google_trends",
                        url=f"https://trends.google.com/trends/explore?q={kw}&geo={region_code}",
                        region=region_code,
                        keywords=[kw],
                        raw_score=score,
                    )
                )

        logger.info(f"Google Trends: collected {len(trends)} trends")
        return trends

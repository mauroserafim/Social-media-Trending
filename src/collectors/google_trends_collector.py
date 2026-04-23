import logging
import time
from typing import Optional

from src.models.trend import RawTrend

logger = logging.getLogger(__name__)

REGIONS = {
    "BR": "brazil",
    "US": "united_states",
}

NICHE_KEYWORDS = {
    "BR": [
        "morar nos EUA",
        "custo de vida EUA",
        "visto americano",
        "green card",
        "trabalho nos Estados Unidos",
        "aluguel nos EUA",
        "salário nos EUA",
        "imigração EUA",
        "dólar hoje",
        "vida nos Estados Unidos",
    ],
    "US": [
        "cost of living",
        "rent prices",
        "immigration USA",
        "minimum wage",
        "housing market",
        "grocery prices",
        "gas prices",
        "inflation 2025",
        "moving to USA",
        "visa application",
    ],
}


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

        # Niche-specific keyword interest
        for region_code, keywords in NICHE_KEYWORDS.items():
            logger.info(f"Collecting Google Trends (niche) for: {region_code}")
            for kw in keywords:
                score = self._fetch_interest(kw, region_code)
                time.sleep(0.5)
                if score > 0:
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

        # General trending searches filtered by region
        for region_code, geo_name in REGIONS.items():
            logger.info(f"Collecting Google Trends (general) for: {region_code}")
            keywords = self._fetch_trending(geo_name)
            time.sleep(1)
            for kw in keywords[:10]:
                trends.append(
                    RawTrend(
                        title=kw,
                        source="google_trends",
                        url=f"https://trends.google.com/trends/explore?q={kw}&geo={region_code}",
                        region=region_code,
                        keywords=[kw],
                        raw_score=20.0,
                    )
                )

        logger.info(f"Google Trends: collected {len(trends)} trends")
        return trends

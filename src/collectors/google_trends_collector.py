import logging
import random
import time

from src.models.trend import RawTrend

logger = logging.getLogger(__name__)

NICHE_KEYWORDS = {
    "BR": [
        "dólar hoje",
        "visto americano",
        "imigração EUA",
        "brasileiro nos EUA",
        "green card",
        "abrir empresa nos EUA",
        "quanto custa viajar para os EUA",
        "inteligência artificial 2025",
        "imposto nos EUA",
        "saúde nos EUA",
        "morar nos EUA",
        "custo de vida EUA",
        "como aprender inglês",
        "renda extra",
        "como ganhar dinheiro online",
        "trabalho home office",
        "vida nos Estados Unidos",
        "como usar inteligência artificial",
    ],
    "US": [
        "minimum wage",
        "cost of living",
        "visa application",
        "AI automation",
        "viral trends",
        "moving to USA",
        "start a business USA",
        "passive income ideas",
        "immigration USA",
        "deportation",
        "green card",
        "healthcare cost",
        "inflation",
        "AI tools for work",
        "best side hustle",
        "digital marketing tips",
        "how to learn online",
    ],
}

# Default score used when pytrends API is unavailable — keeps keywords in the report
DEFAULT_SCORE = 10.0


class GoogleTrendsCollector:
    def __init__(self):
        self._client = None

    def _get_client(self):
        if self._client is None:
            try:
                from pytrends.request import TrendReq
                self._client = TrendReq(
                    hl="pt-BR", tz=360, timeout=(10, 25), retries=2, backoff_factor=1.5
                )
            except ImportError:
                logger.error("pytrends not installed")
                raise
        return self._client

    def _fetch_interest_batch(self, keywords: list[str], geo: str) -> dict[str, float]:
        """Fetch up to 5 keywords in one request. Returns empty dict on failure."""
        try:
            pt = self._get_client()
            kws = keywords[:5]
            pt.build_payload(kws, cat=0, timeframe="now 7-d", geo=geo)
            data = pt.interest_over_time()
            if data.empty:
                logger.warning(f"Google Trends: empty response for {geo} batch {kws}")
                return {}
            return {kw: float(data[kw].mean()) for kw in kws if kw in data.columns}
        except Exception as e:
            logger.warning(f"Google Trends batch failed [{geo}] {keywords[:2]}…: {e}")
            return {}

    def collect(self) -> list[RawTrend]:
        trends: list[RawTrend] = []
        api_working = True

        for region_code, keywords in NICHE_KEYWORDS.items():
            batches = [keywords[i:i + 5] for i in range(0, len(keywords), 5)]
            logger.info(f"Google Trends for {region_code} — {len(batches)} batches")

            for batch in batches:
                scores: dict[str, float] = {}

                if api_working:
                    scores = self._fetch_interest_batch(batch, region_code)
                    if not scores:
                        # First failure — mark API as unavailable and use defaults
                        logger.warning(
                            "Google Trends API unavailable — falling back to default scores"
                        )
                        api_working = False

                for kw in batch:
                    score = scores.get(kw, DEFAULT_SCORE if not api_working else 0.0)
                    if score > 0:
                        trends.append(RawTrend(
                            title=kw,
                            source="google_trends",
                            url=(
                                f"https://trends.google.com/trends/explore"
                                f"?q={kw}&geo={region_code}"
                            ),
                            region=region_code,
                            keywords=[kw],
                            raw_score=score,
                        ))

                if api_working:
                    time.sleep(random.uniform(2.0, 3.5))

        logger.info(
            f"Google Trends: {len(trends)} trends "
            f"({'live scores' if api_working else 'default scores — API blocked'})"
        )
        return trends

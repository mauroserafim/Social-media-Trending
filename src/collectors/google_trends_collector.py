import logging
import random
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
        # Educação & Carreira
        "como aprender inglês",
        "curso online grátis",
        "trabalho home office",
        "como usar inteligência artificial",
        # Negócios & Dinheiro
        "como ganhar dinheiro online",
        "renda extra 2025",
        "dropshipping brasil",
        "abrir empresa nos EUA",
        "afiliados hotmart",
        # Lifestyle & Viagem
        "morar nos EUA",
        "custo de vida EUA",
        "visto americano",
        "quanto custa viajar para os EUA",
        "vida nos Estados Unidos",
        # Tecnologia
        "melhor celular custo benefício",
        "inteligência artificial 2025",
        # Economia & Direito
        "dólar hoje",
        "green card",
        "imigração EUA",
        "imposto nos EUA",
        "saúde nos EUA",
        # Viral & Comunidade
        "memes semana",
        "brasileiro nos EUA",
    ],
    "US": [
        # Education & Career
        "how to learn online",
        "best side hustle 2025",
        "AI tools for work",
        "passive income ideas",
        # Business & Money
        "start a business USA",
        "dropshipping 2025",
        "digital marketing tips",
        # Lifestyle & Travel
        "cost of living",
        "rent prices",
        "moving to USA",
        "travel budget tips",
        # Technology
        "best smartphone 2025",
        "AI automation",
        # Legal & Economy
        "immigration USA",
        "visa application",
        "healthcare cost",
        "inflation 2025",
        "minimum wage",
        "deportation",
        "green card",
        # Viral
        "viral trends",
        "cost of living comparison",
    ],
}


class GoogleTrendsCollector:
    def __init__(self):
        self._client = None

    def _get_client(self):
        if self._client is None:
            try:
                from pytrends.request import TrendReq
                self._client = TrendReq(
                    hl="pt-BR",
                    tz=360,
                    timeout=(10, 25),
                    retries=2,
                    backoff_factor=1.5,
                )
            except ImportError:
                logger.error("pytrends not installed. Run: pip install pytrends")
                raise
        return self._client

    def _fetch_trending(self, geo: str) -> list[str]:
        try:
            pt = self._get_client()
            df = pt.trending_searches(pn=geo)
            return df[0].tolist()
        except Exception as e:
            logger.error(f"Google Trends trending error for {geo}: {e}")
            return []

    def _fetch_interest_batch(self, keywords: list[str], geo: str) -> dict[str, float]:
        """Fetch up to 5 keywords in one request — avoids Google rate limiting."""
        try:
            pt = self._get_client()
            kws = keywords[:5]
            pt.build_payload(kws, cat=0, timeframe="now 1-d", geo=geo)
            data = pt.interest_over_time()
            if data.empty:
                return {}
            return {kw: float(data[kw].mean()) for kw in kws if kw in data.columns}
        except Exception as e:
            logger.warning(f"Google Trends batch failed [{geo}]: {e}")
            return {}

    def collect(self) -> list[RawTrend]:
        trends: list[RawTrend] = []

        # Niche keywords — fetched in batches of 5 (1 request per batch)
        for region_code, keywords in NICHE_KEYWORDS.items():
            batches = [keywords[i:i+5] for i in range(0, len(keywords), 5)]
            logger.info(f"Google Trends (niche) for {region_code} — {len(batches)} batches of ≤5")
            for batch in batches:
                scores = self._fetch_interest_batch(batch, region_code)
                for kw, score in scores.items():
                    if score > 0:
                        trends.append(RawTrend(
                            title=kw,
                            source="google_trends",
                            url=f"https://trends.google.com/trends/explore?q={kw}&geo={region_code}",
                            region=region_code,
                            keywords=[kw],
                            raw_score=score,
                        ))
                # Human-like delay between batches to avoid 429
                time.sleep(random.uniform(2.5, 4.5))

        # General trending (single request per region)
        for region_code, geo_name in REGIONS.items():
            logger.info(f"Google Trends (general) for {region_code}")
            keywords = self._fetch_trending(geo_name)
            time.sleep(random.uniform(1.5, 3.0))
            for kw in keywords[:20]:
                trends.append(RawTrend(
                    title=kw,
                    source="google_trends",
                    url=f"https://trends.google.com/trends/explore?q={kw}&geo={region_code}",
                    region=region_code,
                    keywords=[kw],
                    raw_score=20.0,
                ))

        logger.info(f"Google Trends: collected {len(trends)} trends")
        return trends

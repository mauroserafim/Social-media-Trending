import logging
import time

from src.models.trend import RawTrend

logger = logging.getLogger(__name__)

REGIONS = {
    "BR": "brazil",
    "US": "united_states",
}

# Niche keywords for the "Mecanismo Americano" audience (Brazilians in/going to the US).
# Scored daily via Google Trends interest_over_time() — works on GitHub Actions runners.
NICHE_KEYWORDS = {
    "BR": [
        # Educação & Carreira
        "como aprender inglês",
        "curso online grátis",
        "trabalho home office",
        "como usar inteligência artificial",
        # Negócios & Dinheiro
        "como ganhar dinheiro online",
        "renda extra",
        "abrir empresa nos EUA",
        # Lifestyle & Viagem
        "morar nos EUA",
        "custo de vida EUA",
        "visto americano",
        "quanto custa viajar para os EUA",
        "vida nos Estados Unidos",
        # Tecnologia
        "inteligência artificial 2025",
        # Economia & Direito
        "dólar hoje",
        "green card",
        "imigração EUA",
        "imposto nos EUA",
        "saúde nos EUA",
        # Viral & Comunidade
        "brasileiro nos EUA",
    ],
    "US": [
        # Education & Career
        "how to learn online",
        "best side hustle",
        "AI tools for work",
        "passive income ideas",
        # Business & Money
        "start a business USA",
        "digital marketing tips",
        # Lifestyle & Travel
        "cost of living",
        "moving to USA",
        # Legal & Economy
        "immigration USA",
        "visa application",
        "healthcare cost",
        "inflation",
        "minimum wage",
        "deportation",
        "green card",
        # Viral
        "viral trends",
        "AI automation",
    ],
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

    def _fetch_interest(self, keyword: str, geo: str) -> float:
        try:
            pt = self._get_client()
            pt.build_payload([keyword], cat=0, timeframe="now 7-d", geo=geo)
            data = pt.interest_over_time()
            if data.empty:
                return 0.0
            return float(data[keyword].mean())
        except Exception as e:
            logger.warning(f"Interest fetch failed for '{keyword}' ({geo}): {e}")
            return 0.0

    def collect(self) -> list[RawTrend]:
        trends: list[RawTrend] = []

        for region_code, keywords in NICHE_KEYWORDS.items():
            geo = "BR" if region_code == "BR" else "US"
            logger.info(f"Google Trends (niche keywords) for {region_code} — {len(keywords)} keywords")
            for kw in keywords:
                score = self._fetch_interest(kw, geo)
                time.sleep(0.8)
                if score > 0:
                    trends.append(RawTrend(
                        title=kw,
                        source="google_trends",
                        url=f"https://trends.google.com/trends/explore?q={kw}&geo={region_code}",
                        region=region_code,
                        keywords=[kw],
                        raw_score=score,
                    ))

        logger.info(f"Google Trends: collected {len(trends)} trends")
        return trends

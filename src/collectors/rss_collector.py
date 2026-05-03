import logging
import urllib.parse
from datetime import datetime, timezone
from typing import Optional

import httpx

from src.models.trend import RawTrend

logger = logging.getLogger(__name__)

# Proxy gratuito que funciona de servidores — sem API key necessária
RSS2JSON_BASE = "https://api.rss2json.com/v1/api.json"

RSS_FEEDS = {
    "BR": [
        ("G1 Economia",              "https://g1.globo.com/rss/g1/economia/"),
        ("G1 Brasil",                "https://g1.globo.com/rss/g1/brasil/"),
        ("G1 Mundo",                 "https://g1.globo.com/rss/g1/mundo/"),
        ("CNN Brasil Economia",      "https://www.cnnbrasil.com.br/economia/feed/"),
        ("CNN Brasil Internacional", "https://www.cnnbrasil.com.br/internacional/feed/"),
        ("Exame",                    "https://exame.com/feed/"),
        ("InfoMoney",                "https://www.infomoney.com.br/feed/"),
        ("UOL Notícias",             "https://rss.uol.com.br/feed/noticias.xml"),
    ],
    "US": [
        ("Reuters Business",  "https://feeds.reuters.com/reuters/businessNews"),
        ("Reuters US News",   "https://feeds.reuters.com/Reuters/domesticNews"),
        ("NPR News",          "https://feeds.npr.org/1001/rss.xml"),
        ("NPR Economy",       "https://feeds.npr.org/1006/rss.xml"),
        ("NPR Politics",      "https://feeds.npr.org/1014/rss.xml"),
        ("Axios",             "https://api.axios.com/feed/"),
        ("AP News",           "https://rsshub.app/apnews/topics/apf-topnews"),
        ("The Hill",          "https://thehill.com/rss/syndicator/19110"),
    ],
}


class RSSCollector:
    def __init__(self):
        self.client = httpx.Client(timeout=20, follow_redirects=True)

    def _parse_date(self, raw: Optional[str]) -> Optional[datetime]:
        if not raw:
            return None
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S%z"):
            try:
                dt = datetime.strptime(raw, fmt)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt
            except ValueError:
                continue
        try:
            from email.utils import parsedate_to_datetime
            return parsedate_to_datetime(raw).astimezone(timezone.utc)
        except Exception:
            return None

    def _recency_score(self, published_at: Optional[datetime]) -> float:
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

    def _fetch_via_proxy(self, name: str, url: str) -> list[dict]:
        """Fetch RSS via rss2json.com proxy — bypasses 403 blocks."""
        try:
            r = self.client.get(
                RSS2JSON_BASE,
                params={"rss_url": url, "count": 10},
                timeout=15,
            )
            r.raise_for_status()
            data = r.json()
            if data.get("status") != "ok":
                logger.warning(f"rss2json error [{name}]: {data.get('message', 'unknown')}")
                return []
            items = []
            for item in data.get("items", []):
                title = (item.get("title") or "").strip()
                link = item.get("link") or item.get("guid") or ""
                pub_date = item.get("pubDate") or ""
                if title:
                    items.append({"title": title, "link": link, "pub_date": pub_date})
            return items
        except Exception as e:
            logger.warning(f"RSS proxy fetch failed [{name}]: {e}")
            return []

    def collect(self) -> list[RawTrend]:
        trends: list[RawTrend] = []

        for region, feeds in RSS_FEEDS.items():
            for name, url in feeds:
                logger.info(f"RSS (proxy): collecting {name}")
                items = self._fetch_via_proxy(name, url)
                for item in items:
                    pub_at = self._parse_date(item.get("pub_date"))
                    score = self._recency_score(pub_at)
                    trends.append(RawTrend(
                        title=item["title"],
                        source=f"news:{name}",
                        url=item["link"],
                        published_at=pub_at,
                        region=region,
                        keywords=[],
                        raw_score=score,
                    ))

        logger.info(f"RSS: collected {len(trends)} trends")
        return trends

    def close(self):
        self.client.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

import logging
from datetime import datetime, timezone
from typing import Optional

import feedparser
import httpx

from src.models.trend import RawTrend

logger = logging.getLogger(__name__)

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

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/rss+xml, application/xml, text/xml, */*",
}


class RSSCollector:
    def __init__(self):
        self.client = httpx.Client(timeout=20, follow_redirects=True, headers=HEADERS)

    def _parse_date(self, entry) -> Optional[datetime]:
        # feedparser normalises dates into a time.struct_time in entry.published_parsed
        try:
            import calendar
            t = entry.get("published_parsed") or entry.get("updated_parsed")
            if t:
                return datetime.fromtimestamp(calendar.timegm(t), tz=timezone.utc)
        except Exception:
            pass
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

    def _fetch(self, name: str, url: str) -> list[dict]:
        try:
            r = self.client.get(url, timeout=15)
            r.raise_for_status()
            # Pass raw bytes so feedparser can detect encoding via XML declaration / BOM
            feed = feedparser.parse(r.content)
            if feed.bozo and not feed.entries:
                logger.warning(f"RSS parse warning [{name}]: {feed.bozo_exception}")
                return []
            items = []
            for entry in feed.entries[:10]:
                title = (entry.get("title") or "").strip()
                link = entry.get("link") or entry.get("id") or ""
                if title:
                    items.append({"title": title, "link": link, "entry": entry})
            return items
        except Exception as e:
            logger.warning(f"RSS fetch failed [{name}]: {e}")
            return []

    def collect(self) -> list[RawTrend]:
        trends: list[RawTrend] = []

        for region, feeds in RSS_FEEDS.items():
            for name, url in feeds:
                logger.info(f"RSS: collecting {name}")
                items = self._fetch(name, url)
                for item in items:
                    pub_at = self._parse_date(item["entry"])
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

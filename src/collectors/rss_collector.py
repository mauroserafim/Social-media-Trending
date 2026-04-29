import logging
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Optional
from xml.etree import ElementTree

import httpx

from src.models.trend import RawTrend

logger = logging.getLogger(__name__)

RSS_FEEDS = {
    "BR": [
        ("G1 Economia",         "https://g1.globo.com/rss/g1/economia/"),
        ("G1 Mundo",            "https://g1.globo.com/rss/g1/mundo/"),
        ("G1 Política",        "https://g1.globo.com/rss/g1/politica/"),
        ("G1 Brasil",           "https://g1.globo.com/rss/g1/brasil/"),
        ("CNN Brasil Economia", "https://www.cnnbrasil.com.br/economia/feed/"),
        ("CNN Brasil Internacional", "https://www.cnnbrasil.com.br/internacional/feed/"),
        ("CNN Brasil Política", "https://www.cnnbrasil.com.br/politica/feed/"),
        ("Exame",               "https://exame.com/feed/"),
        ("InfoMoney",           "https://www.infomoney.com.br/feed/"),
        ("UOL Notícias",       "https://rss.uol.com.br/feed/noticias.xml"),
    ],
    "US": [
        ("Reuters Business",    "https://feeds.reuters.com/reuters/businessNews"),
        ("Reuters US News",     "https://feeds.reuters.com/Reuters/domesticNews"),
        ("Reuters World",       "https://feeds.reuters.com/Reuters/worldNews"),
        ("NPR News",            "https://feeds.npr.org/1001/rss.xml"),
        ("NPR Economy",         "https://feeds.npr.org/1006/rss.xml"),
        ("NPR Politics",        "https://feeds.npr.org/1014/rss.xml"),
        ("Axios",               "https://api.axios.com/feed/"),
        ("Bloomberg Economy",   "https://feeds.bloomberg.com/economics/news.rss"),
        ("AP News",             "https://rsshub.app/apnews/topics/apf-topnews"),
        ("Pew Research",        "https://www.pewresearch.org/feed/"),
    ],
}


class RSSCollector:
    def __init__(self):
        self.client = httpx.Client(
            timeout=20,
            follow_redirects=True,
            headers={"User-Agent": "Mozilla/5.0 (compatible; TrendsBot/2.0)"},
        )

    def _parse_date(self, raw: Optional[str]) -> Optional[datetime]:
        if not raw:
            return None
        try:
            return parsedate_to_datetime(raw).astimezone(timezone.utc)
        except Exception:
            try:
                return datetime.fromisoformat(raw.replace("Z", "+00:00"))
            except Exception:
                return None

    def _recency_score(self, published_at: Optional[datetime]) -> float:
        if not published_at:
            return 30.0
        now = datetime.now(timezone.utc)
        hours_old = (now - published_at).total_seconds() / 3600
        if hours_old < 1:
            return 100.0
        if hours_old < 6:
            return 80.0
        if hours_old < 24:
            return 60.0
        if hours_old < 72:
            return 40.0
        return 20.0

    def _fetch_feed(self, name: str, url: str) -> list[dict]:
        try:
            response = self.client.get(url)
            response.raise_for_status()
            root = ElementTree.fromstring(response.content)
            ns = {"atom": "http://www.w3.org/2005/Atom"}
            items = []

            # RSS 2.0
            for item in root.findall(".//item"):
                title = item.findtext("title", "").strip()
                link = item.findtext("link", "").strip()
                pub_date = item.findtext("pubDate")
                if title:
                    items.append({"title": title, "link": link, "pub_date": pub_date})

            # Atom
            for entry in root.findall(".//atom:entry", ns):
                title_el = entry.find("atom:title", ns)
                link_el = entry.find("atom:link", ns)
                updated_el = entry.find("atom:updated", ns)
                title = title_el.text.strip() if title_el is not None and title_el.text else ""
                link = link_el.get("href", "") if link_el is not None else ""
                pub_date = updated_el.text if updated_el is not None else None
                if title:
                    items.append({"title": title, "link": link, "pub_date": pub_date})

            return items
        except Exception as e:
            logger.warning(f"RSS fetch failed [{name}]: {e}")
            return []

    def collect(self) -> list[RawTrend]:
        trends: list[RawTrend] = []

        for region, feeds in RSS_FEEDS.items():
            for name, url in feeds:
                logger.info(f"RSS: collecting {name}")
                items = self._fetch_feed(name, url)
                for item in items[:10]:
                    pub_at = self._parse_date(item.get("pub_date"))
                    score = self._recency_score(pub_at)
                    trends.append(RawTrend(
                        title=item["title"],
                        source=f"rss:{name}",
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

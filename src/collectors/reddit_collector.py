import logging
import time
from datetime import datetime, timezone

import httpx

from src.models.trend import RawTrend

logger = logging.getLogger(__name__)

# Subreddits mapped by region — general trending, not niche-filtered
SUBREDDITS: dict[str, list[str]] = {
    "BR": [
        "brasil",
        "investimentos",
        "noticias",
        "desabafos",
        "empreendedorismo",
        "economia",
        "direito",
        "geopolitica",
    ],
    "US": [
        "news",
        "worldnews",
        "politics",
        "economy",
        "personalfinance",
        "immigration",
        "antiwork",
        "AskAmerican",
        "unitedstates",
        "TrueOffMyChest",
        "conspiracy",
    ],
}


class RedditCollector:
    def __init__(self):
        self.client = httpx.Client(
            timeout=30,
            headers={
                "User-Agent": "TrendsResearchBot/2.0 (educational research)",
                "Accept": "application/json",
            },
            follow_redirects=True,
        )

    def _fetch_hot(self, subreddit: str, limit: int = 20) -> list[dict]:
        try:
            url = f"https://www.reddit.com/r/{subreddit}/hot.json?limit={limit}"
            resp = self.client.get(url)
            resp.raise_for_status()
            return resp.json().get("data", {}).get("children", [])
        except Exception as e:
            logger.warning(f"Reddit r/{subreddit} failed: {e}")
            return []

    def _hours_old(self, created_utc: float) -> float:
        now = datetime.now(timezone.utc)
        pub = datetime.fromtimestamp(created_utc, tz=timezone.utc)
        return max((now - pub).total_seconds() / 3600, 0.1)

    def _score(self, ups: int, comments: int, hours: float) -> float:
        # Weight comments more — they indicate discussion depth
        engagement = ups + comments * 3
        velocity = engagement / hours
        return min(round(velocity / 5, 2), 100.0)

    def collect(self) -> list[RawTrend]:
        trends: list[RawTrend] = []

        for region, subs in SUBREDDITS.items():
            for sub in subs:
                logger.info(f"Reddit: collecting r/{sub}")
                posts = self._fetch_hot(sub)
                for item in posts:
                    post = item.get("data", {})
                    if post.get("stickied") or post.get("pinned"):
                        continue
                    title = post.get("title", "").strip()
                    if not title:
                        continue
                    ups = post.get("ups", 0)
                    comments = post.get("num_comments", 0)
                    created = post.get("created_utc", 0)
                    pub_at = datetime.fromtimestamp(created, tz=timezone.utc) if created else None
                    hours = self._hours_old(created) if created else 24.0
                    trends.append(
                        RawTrend(
                            title=title,
                            source=f"reddit:r/{sub}",
                            url=f"https://reddit.com{post.get('permalink', '')}",
                            published_at=pub_at,
                            region=region,
                            keywords=[sub],
                            raw_score=self._score(ups, comments, hours),
                            views=ups,
                        )
                    )
                # Avoid rate limiting
                time.sleep(0.3)

        logger.info(f"Reddit: collected {len(trends)} trends")
        return trends

    def close(self):
        self.client.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

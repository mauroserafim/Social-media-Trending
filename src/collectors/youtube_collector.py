import logging
import os
from datetime import datetime, timezone
from typing import Optional

import httpx

from src.models.trend import RawTrend

logger = logging.getLogger(__name__)

YOUTUBE_API_BASE = "https://www.googleapis.com/youtube/v3"
REGIONS = ["BR", "US"]

# US: exclude Music=10, Gaming=20, Film & Animation=1, Sports=17
EXCLUDED_CATEGORY_IDS_US = {"1", "10", "17", "20"}
# BR: only exclude Gaming — music/sports/entertainment are genuinely trending there
EXCLUDED_CATEGORY_IDS_BR = {"20"}

# US-only keyword filter (Brazilian trending content is different — don't over-filter)
EXCLUDED_TITLE_KEYWORDS_US = {
    # Games
    "gameplay", "gaming", "gamer", "streamer",
    "minecraft", "roblox", "fortnite", "valorant", "apex legends",
    "free fire", "league of legends", "counter strike", "grand theft",
    "among us", "call of duty", "gta", "zelda", "pokemon",
    # Music / Clips
    "official mv", "music video", "official audio",
    "lyric video", "lyrics", "official lyric",
    # Trailers
    "official trailer", "teaser trailer",
    "trailer breakdown",
    "netflix", "disney+", "hbo max", "prime video", "apple tv+",
    "season", "episode",
    # Sports teams (US)
    "sabres", "bruins", "lightning", "canadiens", "maple leafs", "rangers",
    "penguins", "flyers", "capitals", "islanders", "blackhawks", "red wings",
    "wild at", "avalanche", "flames", "oilers", "jets", "predators",
    "knicks", "lakers", "celtics", "warriors", "heat", "bulls", "nets",
    "hawks", "cavaliers", "pistons", "pacers", "bucks", "raptors",
    "phillies", "marlins", "yankees", "red sox", "dodgers", "mets",
    "eagles", "cowboys", "patriots", "49ers", "chiefs",
    "nba", "nfl", "nhl", "mlb", "wnba", "mls", "nascar", "wwe", "ufc",
    "first round", "playoffs", "shoot-out", "smackdown",
    "speedycash", "klondike",
}

# BR: only block pure gaming content with no content value
EXCLUDED_TITLE_KEYWORDS_BR = {
    "gameplay", "gaming", "gamer", "streamer",
    "minecraft", "roblox", "fortnite", "valorant", "apex legends",
    "free fire", "league of legends", "counter strike", "grand theft",
    "among us", "call of duty", "gta", "zelda", "pokemon",
    "troll de", "torre troll",
}


class YouTubeCollector:
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("YOUTUBE_API_KEY", "")
        self.client = httpx.Client(timeout=30)

    def _get_trending_videos(self, region: str, max_results: int = 50) -> list[dict]:
        if not self.api_key:
            logger.warning("YouTube API key not set, skipping YouTube collection")
            return []

        params = {
            "part": "snippet,statistics",
            "chart": "mostPopular",
            "regionCode": region,
            "maxResults": max_results,
            "key": self.api_key,
        }
        try:
            response = self.client.get(f"{YOUTUBE_API_BASE}/videos", params=params)
            response.raise_for_status()
            return response.json().get("items", [])
        except httpx.HTTPError as e:
            logger.error(f"YouTube API error for region {region}: {e}")
            return []

    def _parse_published_at(self, raw: str) -> Optional[datetime]:
        try:
            return datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except Exception:
            return None

    def _calc_views_per_hour(self, views: int, published_at: Optional[datetime]) -> Optional[float]:
        if not published_at:
            return None
        now = datetime.now(timezone.utc)
        hours = max((now - published_at).total_seconds() / 3600, 1)
        return round(views / hours, 2)

    def _score(self, views: int, views_per_hour: Optional[float]) -> float:
        base = min(views / 1_000_000, 50)
        velocity = min((views_per_hour or 0) / 10_000, 50)
        return round(base + velocity, 2)

    def collect(self, regions: list[str] = REGIONS) -> list[RawTrend]:
        trends: list[RawTrend] = []
        for region in regions:
            logger.info(f"Collecting YouTube trending for region: {region}")
            videos = self._get_trending_videos(region, max_results=50)
            excluded_cats = EXCLUDED_CATEGORY_IDS_US if region == "US" else EXCLUDED_CATEGORY_IDS_BR
            excluded_kws = EXCLUDED_TITLE_KEYWORDS_US if region == "US" else EXCLUDED_TITLE_KEYWORDS_BR
            skipped = 0
            for item in videos:
                snippet = item.get("snippet", {})
                stats = item.get("statistics", {})
                category = snippet.get("categoryId", "")
                title_lower = snippet.get("title", "").lower()
                if category in excluded_cats:
                    skipped += 1
                    continue
                if any(kw in title_lower for kw in excluded_kws):
                    skipped += 1
                    continue
                views = int(stats.get("viewCount", 0))
                pub_at = self._parse_published_at(snippet.get("publishedAt", ""))
                vph = self._calc_views_per_hour(views, pub_at)
                video_id = item.get("id", "")
                trends.append(
                    RawTrend(
                        title=snippet.get("title", ""),
                        source="youtube",
                        url=f"https://youtube.com/watch?v={video_id}",
                        views=views,
                        views_per_hour=vph,
                        published_at=pub_at,
                        region=region,
                        keywords=snippet.get("tags", [])[:10] + ([category] if category else []),
                        raw_score=self._score(views, vph),
                    )
                )
            logger.info(f"YouTube {region}: {len(videos) - skipped} kept, {skipped} filtered (music/gaming/film)")
        logger.info(f"YouTube: collected {len(trends)} trends total")
        return trends

    def close(self):
        self.client.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

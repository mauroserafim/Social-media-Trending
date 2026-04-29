import logging

import httpx

from src.models.trend import RawTrend

logger = logging.getLogger(__name__)

# TikTok Creative Center — hashtag and video trend endpoints (public, no auth)
CC_HASHTAG_URL = "https://ads.tiktok.com/creative_radar_api/v1/popular_trend/hashtag/list"
CC_VIDEO_URL = "https://ads.tiktok.com/creative_radar_api/v1/popular_trend/video/list"

REGIONS = ["US", "BR"]

CC_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://ads.tiktok.com/business/creativecenter/trending-hashtags/pc/en",
    "Origin": "https://ads.tiktok.com",
}


class TikTokCollector:
    def __init__(self):
        self.client = httpx.Client(
            timeout=30,
            headers=CC_HEADERS,
            follow_redirects=True,
        )

    def _fetch(self, url: str, country: str, limit: int = 10) -> list[dict]:
        try:
            params = {"period": 7, "page": 1, "limit": limit, "country_code": country, "sort_by": "popular"}
            resp = self.client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()
            return data.get("data", {}).get("list", [])
        except Exception as e:
            logger.warning(f"TikTok endpoint {url} failed for {country}: {e}")
            return []

    def collect(self) -> list[RawTrend]:
        trends: list[RawTrend] = []

        for region in REGIONS:
            logger.info(f"TikTok: collecting for {region}")

            # Hashtags
            for item in self._fetch(CC_HASHTAG_URL, region):
                name = item.get("hashtag_name", "").strip()
                if not name:
                    continue
                views = item.get("video_views", 0) or 0
                trends.append(RawTrend(
                    title=f"#{name}",
                    source="tiktok",
                    url=f"https://www.tiktok.com/tag/{name}",
                    region=region,
                    keywords=[name],
                    raw_score=min(round(views / 1_000_000, 2), 100.0),
                    views=int(views),
                ))

            # Viral videos
            for item in self._fetch(CC_VIDEO_URL, region):
                desc = item.get("video_description", "").strip() or item.get("title", "").strip()
                if not desc:
                    continue
                views = item.get("vv", 0) or item.get("play_count", 0) or 0
                url = item.get("video_url", "") or f"https://www.tiktok.com/"
                trends.append(RawTrend(
                    title=desc[:120],
                    source="tiktok",
                    url=url,
                    region=region,
                    keywords=[],
                    raw_score=min(round(views / 1_000_000, 2), 100.0),
                    views=int(views),
                ))

        if not trends:
            logger.warning("TikTok: no data collected (Creative Center API unavailable without auth)")
        else:
            logger.info(f"TikTok: collected {len(trends)} trends")

        return trends

    def close(self):
        self.client.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

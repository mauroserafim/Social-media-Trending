import logging

import httpx

from src.models.trend import RawTrend

logger = logging.getLogger(__name__)

# TikTok Creative Center public API — no auth required
TIKTOK_CC_URL = "https://ads.tiktok.com/creative_radar_api/v1/popular_trend/hashtag/list"

REGIONS = ["US", "BR"]


class TikTokCollector:
    def __init__(self):
        self.client = httpx.Client(
            timeout=30,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                ),
                "Accept": "application/json, text/plain, */*",
                "Referer": "https://ads.tiktok.com/business/creativecenter/",
                "Origin": "https://ads.tiktok.com",
            },
            follow_redirects=True,
        )

    def _fetch_hashtags(self, country: str, limit: int = 10) -> list[dict]:
        try:
            params = {
                "period": 7,
                "page": 1,
                "limit": limit,
                "country_code": country,
                "sort_by": "popular",
            }
            resp = self.client.get(TIKTOK_CC_URL, params=params)
            resp.raise_for_status()
            data = resp.json()
            # Response: {"data": {"list": [{"hashtag_name": "...", "video_views": N, ...}]}}
            return data.get("data", {}).get("list", [])
        except Exception as e:
            logger.warning(f"TikTok Creative Center unavailable for {country}: {e}")
            return []

    def collect(self) -> list[RawTrend]:
        trends: list[RawTrend] = []

        for region in REGIONS:
            logger.info(f"TikTok: collecting trending hashtags for {region}")
            hashtags = self._fetch_hashtags(region)

            for item in hashtags:
                name = item.get("hashtag_name", "").strip()
                if not name:
                    continue
                views = item.get("video_views", 0) or item.get("publish_cnt", 0) or 0
                score = min(round(views / 1_000_000, 2), 100.0)
                trends.append(
                    RawTrend(
                        title=f"#{name}",
                        source="tiktok",
                        url=f"https://www.tiktok.com/tag/{name}",
                        region=region,
                        keywords=[name],
                        raw_score=score,
                        views=int(views),
                    )
                )

        if not trends:
            logger.warning("TikTok: no data collected (Creative Center API may require auth)")
        else:
            logger.info(f"TikTok: collected {len(trends)} trends")

        return trends

    def close(self):
        self.client.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

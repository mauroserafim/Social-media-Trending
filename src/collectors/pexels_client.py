import logging
import os
from typing import Optional

import httpx
from pydantic import BaseModel

logger = logging.getLogger(__name__)

PEXELS_API_BASE = "https://api.pexels.com/v1"


class PexelsPhoto(BaseModel):
    id: int
    photographer: str
    photographer_url: str
    pexels_url: str
    download_url: str  # "large" size — good balance for carousel slides


class PexelsClient:
    """Free stock-photo search via the Pexels API.

    Free tier: 200 requests/hour, 20,000/month. No attribution legally
    required by the Pexels license, but we credit the photographer anyway
    for professionalism. Get a free key at https://www.pexels.com/api/
    """

    def __init__(self, api_key: Optional[str] = None):
        # .strip(): a stray trailing space/newline from copy-pasting the key into
        # GitHub Secrets makes httpx reject it as an "Illegal header value".
        self.api_key = (api_key or os.getenv("PEXELS_API_KEY", "")).strip()
        self.client = httpx.Client(timeout=30)

    def is_configured(self) -> bool:
        return bool(self.api_key)

    def search_photo(self, query: str, orientation: str = "portrait") -> Optional[PexelsPhoto]:
        """Return the top matching photo for query, or None if unavailable/not found."""
        if not self.api_key:
            logger.warning("PEXELS_API_KEY not set, skipping image search")
            return None

        try:
            response = self.client.get(
                f"{PEXELS_API_BASE}/search",
                headers={"Authorization": self.api_key},
                params={"query": query, "per_page": 1, "orientation": orientation},
            )
            response.raise_for_status()
            photos = response.json().get("photos", [])
            if not photos:
                logger.warning(f"No Pexels results for query: '{query}'")
                return None

            photo = photos[0]
            return PexelsPhoto(
                id=photo["id"],
                photographer=photo.get("photographer", "Pexels"),
                photographer_url=photo.get("photographer_url", "https://www.pexels.com"),
                pexels_url=photo.get("url", ""),
                download_url=photo["src"].get("large", photo["src"].get("original", "")),
            )
        except httpx.HTTPError as e:
            logger.error(f"Pexels API error for query '{query}': {e}")
            return None

    def download(self, photo: PexelsPhoto, dest_path: str) -> bool:
        try:
            response = self.client.get(photo.download_url)
            response.raise_for_status()
            with open(dest_path, "wb") as f:
                f.write(response.content)
            return True
        except (httpx.HTTPError, OSError) as e:
            logger.error(f"Failed to download Pexels photo {photo.id}: {e}")
            return False

    def close(self):
        self.client.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

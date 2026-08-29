import re
import unicodedata
from datetime import datetime

from pydantic import BaseModel, Field


def slugify(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    normalized = re.sub(r"[^a-zA-Z0-9]+", "-", normalized).strip("-").lower()
    return normalized[:80]


class Source(BaseModel):
    label: str
    url: str = ""


class CarouselSlide(BaseModel):
    number: int
    headline: str
    body: str
    visual_direction: str = ""
    image_query: str = ""  # short English keyword phrase for stock photo search
    image_path: str = ""  # local path to the downloaded photo, if any
    image_credit: str = ""  # e.g. "Foto: Jane Doe (Pexels)"
    image_source_url: str = ""


class CarouselPost(BaseModel):
    topic: str
    topic_slug: str = ""
    region: str = "US-BR"
    hook: str
    slides: list[CarouselSlide] = Field(default_factory=list)
    caption_instagram: str = ""
    caption_tiktok: str = ""
    hashtags_instagram: list[str] = Field(default_factory=list)
    hashtags_tiktok: list[str] = Field(default_factory=list)
    sources: list[Source] = Field(default_factory=list)
    cta: str = ""
    best_posting_time_brt: str = ""
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    run_id: str = ""

    def model_post_init(self, __context) -> None:
        if not self.topic_slug:
            self.topic_slug = slugify(self.topic)

    def to_dict(self) -> dict:
        data = self.model_dump()
        data["generated_at"] = self.generated_at.isoformat()
        return data

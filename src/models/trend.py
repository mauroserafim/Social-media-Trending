from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from enum import Enum


class VideoFormat(str, Enum):
    SHORT = "short"
    LONG = "long"
    BOTH = "both"


class UrgencyLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class RawTrend(BaseModel):
    title: str
    source: str
    url: Optional[str] = None
    views: Optional[int] = None
    views_per_hour: Optional[float] = None
    growth_rate: Optional[float] = None
    published_at: Optional[datetime] = None
    region: Optional[str] = None
    keywords: list[str] = Field(default_factory=list)
    raw_score: float = 0.0


class TrendIdea(BaseModel):
    main_topic: str
    subtopic: str
    score: float = Field(ge=0, le=100)
    why_trending: str
    links: list[str] = Field(default_factory=list)
    hook: str
    titles: list[str] = Field(min_length=3, max_length=3)
    thumbnails: list[str] = Field(min_length=3, max_length=3)
    video_format: VideoFormat
    urgency: UrgencyLevel
    ease: int = Field(ge=1, le=10, description="1=hard 10=easy")
    source: str
    region: str
    collected_at: datetime = Field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict:
        data = self.model_dump()
        data["collected_at"] = self.collected_at.isoformat()
        data["video_format"] = self.video_format.value
        data["urgency"] = self.urgency.value
        return data

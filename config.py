import os
from dataclasses import dataclass, field


@dataclass
class Config:
    # API Keys
    openai_api_key: str = field(default_factory=lambda: os.getenv("OPENAI_API_KEY", ""))
    youtube_api_key: str = field(default_factory=lambda: os.getenv("YOUTUBE_API_KEY", ""))
    pexels_api_key: str = field(default_factory=lambda: os.getenv("PEXELS_API_KEY", ""))

    # OpenAI
    openai_model: str = field(default_factory=lambda: os.getenv("OPENAI_MODEL", "gpt-4o-mini"))

    # Agent
    max_ideas: int = field(default_factory=lambda: int(os.getenv("MAX_IDEAS", "10")))
    regions: list[str] = field(default_factory=lambda: os.getenv("REGIONS", "BR,US").split(","))

    # Storage
    db_path: str = field(default_factory=lambda: os.getenv("DB_PATH", "data/trends.db"))

    # API Server
    port: int = field(default_factory=lambda: int(os.getenv("PORT", "8000")))
    host: str = field(default_factory=lambda: os.getenv("HOST", "0.0.0.0"))

    def validate(self) -> list[str]:
        errors = []
        if not self.openai_api_key:
            errors.append("OPENAI_API_KEY is required")
        return errors


config = Config()

import json
import logging
import os
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional

from src.models.trend import RawTrend, TrendIdea

logger = logging.getLogger(__name__)

DB_PATH = os.getenv("DB_PATH", "data/trends.db")


class Database:
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn: Optional[sqlite3.Connection] = None
        self._init_schema()

    @property
    def conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(self.db_path)
            self._conn.row_factory = sqlite3.Row
        return self._conn

    def _init_schema(self):
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS raw_trends (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                source TEXT NOT NULL,
                url TEXT,
                views INTEGER,
                views_per_hour REAL,
                growth_rate REAL,
                published_at TEXT,
                region TEXT,
                keywords TEXT,
                raw_score REAL,
                collected_at TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS trend_ideas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                main_topic TEXT NOT NULL,
                subtopic TEXT,
                score REAL NOT NULL,
                why_trending TEXT,
                links TEXT,
                hook TEXT,
                titles TEXT,
                thumbnails TEXT,
                video_format TEXT,
                urgency TEXT,
                ease INTEGER,
                source TEXT,
                region TEXT,
                collected_at TEXT,
                run_id TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_trend_ideas_score ON trend_ideas(score DESC);
            CREATE INDEX IF NOT EXISTS idx_trend_ideas_collected ON trend_ideas(collected_at DESC);
            CREATE INDEX IF NOT EXISTS idx_raw_trends_collected ON raw_trends(collected_at DESC);
        """)
        self.conn.commit()

    def save_raw_trends(self, trends: list[RawTrend]) -> int:
        rows = [
            (
                t.title,
                t.source,
                t.url,
                t.views,
                t.views_per_hour,
                t.growth_rate,
                t.published_at.isoformat() if t.published_at else None,
                t.region,
                json.dumps(t.keywords, ensure_ascii=False),
                t.raw_score,
            )
            for t in trends
        ]
        self.conn.executemany(
            """INSERT INTO raw_trends
               (title, source, url, views, views_per_hour, growth_rate, published_at,
                region, keywords, raw_score)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            rows,
        )
        self.conn.commit()
        return len(rows)

    def save_trend_ideas(self, ideas: list[TrendIdea], run_id: str = "") -> int:
        rows = [
            (
                idea.main_topic,
                idea.subtopic,
                idea.score,
                idea.why_trending,
                json.dumps(idea.links, ensure_ascii=False),
                idea.hook,
                json.dumps(idea.titles, ensure_ascii=False),
                json.dumps(idea.thumbnails, ensure_ascii=False),
                idea.video_format.value,
                idea.urgency.value,
                idea.ease,
                idea.source,
                idea.region,
                idea.collected_at.isoformat(),
                run_id,
            )
            for idea in ideas
        ]
        self.conn.executemany(
            """INSERT INTO trend_ideas
               (main_topic, subtopic, score, why_trending, links, hook, titles,
                thumbnails, video_format, urgency, ease, source, region, collected_at, run_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            rows,
        )
        self.conn.commit()
        return len(rows)

    def get_latest_ideas(self, limit: int = 20) -> list[dict]:
        cursor = self.conn.execute(
            "SELECT * FROM trend_ideas ORDER BY collected_at DESC, score DESC LIMIT ?",
            (limit,),
        )
        return [dict(row) for row in cursor.fetchall()]

    def close(self):
        if self._conn:
            self._conn.close()
            self._conn = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

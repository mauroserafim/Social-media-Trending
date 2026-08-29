import json
import logging
import os
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional

from src.models.carousel import CarouselPost
from src.models.trend import NicheIdea, RawTrend, TrendIdea

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

            CREATE TABLE IF NOT EXISTS niche_ideas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                main_topic TEXT NOT NULL,
                subtopic TEXT,
                why_trending TEXT,
                niche_angle TEXT,
                video_format TEXT,
                urgency TEXT,
                ease INTEGER,
                source TEXT,
                region TEXT,
                links TEXT,
                platforms TEXT,
                collected_at TEXT,
                run_id TEXT
            );

            CREATE TABLE IF NOT EXISTS carousel_posts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                topic TEXT NOT NULL,
                topic_slug TEXT NOT NULL,
                region TEXT,
                hook TEXT,
                payload TEXT NOT NULL,
                generated_at TEXT,
                run_id TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_niche_ideas_collected ON niche_ideas(collected_at DESC);
            CREATE INDEX IF NOT EXISTS idx_raw_trends_collected ON raw_trends(collected_at DESC);
            CREATE INDEX IF NOT EXISTS idx_raw_trends_source ON raw_trends(source);
            CREATE INDEX IF NOT EXISTS idx_carousel_posts_slug ON carousel_posts(topic_slug);
            CREATE INDEX IF NOT EXISTS idx_carousel_posts_generated ON carousel_posts(generated_at DESC);
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

    def save_niche_ideas(self, ideas: list[NicheIdea], run_id: str = "") -> int:
        rows = [
            (
                idea.main_topic,
                idea.subtopic,
                idea.why_trending,
                idea.niche_angle,
                idea.video_format.value,
                idea.urgency.value,
                idea.ease,
                idea.source,
                idea.region,
                json.dumps(idea.links, ensure_ascii=False),
                json.dumps(idea.platforms, ensure_ascii=False),
                idea.collected_at.isoformat(),
                run_id,
            )
            for idea in ideas
        ]
        self.conn.executemany(
            """INSERT INTO niche_ideas
               (main_topic, subtopic, why_trending, niche_angle, video_format, urgency,
                ease, source, region, links, platforms, collected_at, run_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            rows,
        )
        self.conn.commit()
        return len(rows)

    def get_latest_niche_ideas(self, limit: int = 20) -> list[dict]:
        cursor = self.conn.execute(
            "SELECT * FROM niche_ideas ORDER BY collected_at DESC LIMIT ?",
            (limit,),
        )
        return [dict(row) for row in cursor.fetchall()]

    def save_carousel_post(self, post: CarouselPost) -> int:
        self.conn.execute(
            """INSERT INTO carousel_posts
               (topic, topic_slug, region, hook, payload, generated_at, run_id)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                post.topic,
                post.topic_slug,
                post.region,
                post.hook,
                json.dumps(post.to_dict(), ensure_ascii=False),
                post.generated_at.isoformat(),
                post.run_id,
            ),
        )
        self.conn.commit()
        return self.conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    def get_recent_carousel_topics(self, limit: int = 60) -> list[dict]:
        cursor = self.conn.execute(
            """SELECT topic, topic_slug, generated_at FROM carousel_posts
               ORDER BY generated_at DESC LIMIT ?""",
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

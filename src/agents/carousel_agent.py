import json
import logging
import os
import uuid
from datetime import datetime
from pathlib import Path

from src.analyzers.carousel_generator import CarouselGenerator
from src.collectors.pexels_client import PexelsClient
from src.exporters.carousel_json_exporter import CarouselJSONExporter
from src.exporters.carousel_markdown_exporter import CarouselMarkdownExporter
from src.models.carousel import CarouselPost, slugify
from src.storage.database import Database

logger = logging.getLogger(__name__)

# The sqlite DB (data/*.db) is gitignored and does NOT survive between GitHub
# Actions runs — each run starts from a fresh checkout. outputs/ IS committed
# after every run, so the dedup history lives here to reliably prevent
# repeated topics day over day, both locally and in CI.
HISTORY_PATH = Path("outputs/carousel/history.json")
HISTORY_MAX_ENTRIES = 200
IMAGES_DIR = Path("outputs/carousel/images")

# Fallback topics used only when there are no fresh niche ideas in the database
# (e.g. first run, or trends agent hasn't run yet today).
FALLBACK_TOPICS = [
    {
        "main_topic": "Quanto custa viver nos EUA de verdade",
        "subtopic": "Aluguel, saúde e mercado comparados ao Brasil",
        "why_trending": "Tema evergreen: brasileiros pesquisam constantemente custo de vida nos EUA",
        "niche_angle": "Comparação direta de preços com fontes oficiais (BLS, Numbeo)",
        "region": "US-BR",
    },
    {
        "main_topic": "Como funciona o sistema de crédito americano",
        "subtopic": "Credit score, o que brasileiro recém-chegado não sabe",
        "why_trending": "Tema evergreen para quem está migrando ou pensando em migrar",
        "niche_angle": "Passo a passo prático + armadilhas comuns de imigrantes",
        "region": "US",
    },
    {
        "main_topic": "Diferenças culturais que chocam brasileiros nos EUA",
        "subtopic": "Trabalho, amizade e comunicação direta americana",
        "why_trending": "Tema evergreen de alto engajamento e identificação",
        "niche_angle": "Choque cultural real, com exemplos do dia a dia",
        "region": "US-BR",
    },
]


class CarouselAgent:
    def __init__(self):
        self.run_id = os.getenv("GITHUB_RUN_ID", str(uuid.uuid4())[:8])
        self.generator = CarouselGenerator()
        self.pexels = PexelsClient()
        self.db = Database()
        self.md_exp = CarouselMarkdownExporter()
        self.json_exp = CarouselJSONExporter()

    def _load_history(self) -> list[dict]:
        if not HISTORY_PATH.exists():
            return []
        try:
            return json.loads(HISTORY_PATH.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(f"Could not read carousel history, starting fresh: {e}")
            return []

    def _append_history(self, post: CarouselPost, history: list[dict]) -> None:
        history.append({
            "topic": post.topic,
            "topic_slug": post.topic_slug,
            "generated_at": post.generated_at.isoformat(),
        })
        history = history[-HISTORY_MAX_ENTRIES:]
        HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
        HISTORY_PATH.write_text(json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8")

    def _pick_topic(self, used_slugs: set[str]) -> dict:
        rows = self.db.get_latest_niche_ideas(limit=50)
        for row in rows:
            slug = slugify(row["main_topic"])
            if slug not in used_slugs:
                return {
                    "main_topic": row["main_topic"],
                    "subtopic": row.get("subtopic", ""),
                    "why_trending": row.get("why_trending", ""),
                    "niche_angle": row.get("niche_angle", ""),
                    "region": row.get("region", "US-BR"),
                }

        for topic in FALLBACK_TOPICS:
            if slugify(topic["main_topic"]) not in used_slugs:
                return topic

        # Everything has been used recently — pick the least-recently-used niche idea anyway
        # rather than blocking the daily post.
        if rows:
            row = rows[0]
            return {
                "main_topic": f"{row['main_topic']} — outro ângulo",
                "subtopic": row.get("subtopic", ""),
                "why_trending": row.get("why_trending", ""),
                "niche_angle": row.get("niche_angle", ""),
                "region": row.get("region", "US-BR"),
            }
        return FALLBACK_TOPICS[0]

    def _fetch_images(self, post: CarouselPost) -> None:
        """Search a free stock-photo bank (Pexels) for each slide's image_query
        and download a matching photo. Mutates post.slides in place. Skips
        silently (leaving slides without images) if PEXELS_API_KEY isn't set
        or a given query has no results — the text/design brief still works
        without photos."""
        if not self.pexels.is_configured():
            logger.warning("PEXELS_API_KEY not set — skipping image download for slides")
            return

        post_subdir = f"{post.topic_slug}_{post.generated_at.strftime('%Y%m%d_%H%M%S')}"
        post_dir = IMAGES_DIR / post_subdir
        post_dir.mkdir(parents=True, exist_ok=True)

        for slide in post.slides:
            query = slide.image_query or slide.headline
            if not query:
                continue
            photo = self.pexels.search_photo(query)
            if photo is None:
                continue
            filename = f"slide_{slide.number}.jpg"
            dest = post_dir / filename
            if self.pexels.download(photo, str(dest)):
                # Relative to outputs/carousel/ (where the .md lives) — not the
                # full "outputs/carousel/images/..." path — so the image link
                # resolves both when opening outputs/carousel/latest.md locally
                # and inside the CI artifact zip (whose root IS outputs/carousel/).
                slide.image_path = f"images/{post_subdir}/{filename}"
                slide.image_credit = f"Foto: {photo.photographer} (Pexels)"
                slide.image_source_url = photo.pexels_url

        found = sum(1 for s in post.slides if s.image_path)
        logger.info(f"Images: {found}/{len(post.slides)} slides matched with a Pexels photo")

    def run(self) -> CarouselPost | None:
        start = datetime.utcnow()
        logger.info(f"=== Carousel Agent started | run_id={self.run_id} ===")

        history = self._load_history()
        # Also merge in whatever the local sqlite DB knows (useful for local/dev runs
        # between resets), even though it won't persist across CI runs.
        db_recent = self.db.get_recent_carousel_topics(limit=60)

        used_topics = [h["topic"] for h in history] + [r["topic"] for r in db_recent]
        used_slugs = {h["topic_slug"] for h in history} | {r["topic_slug"] for r in db_recent}

        candidate = self._pick_topic(used_slugs)
        logger.info(f"Selected topic: {candidate['main_topic']}")

        post = self.generator.generate(
            main_topic=candidate["main_topic"],
            subtopic=candidate.get("subtopic", ""),
            why_trending=candidate.get("why_trending", ""),
            niche_angle=candidate.get("niche_angle", ""),
            region=candidate.get("region", "US-BR"),
            used_topics=used_topics,
            run_id=self.run_id,
        )

        if post is None:
            logger.error("Carousel generation failed — no post produced")
            return None

        self._fetch_images(post)

        self.db.save_carousel_post(post)
        self._append_history(post, history)
        md_path = self.md_exp.export(post)
        json_path = self.json_exp.export(post)
        logger.info(f"Exported: {md_path}, {json_path}")

        elapsed = (datetime.utcnow() - start).total_seconds()
        logger.info(f"=== Done in {elapsed:.1f}s | topic='{post.topic}' | {len(post.slides)} slides ===")
        return post

    def close(self):
        self.pexels.close()
        self.db.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

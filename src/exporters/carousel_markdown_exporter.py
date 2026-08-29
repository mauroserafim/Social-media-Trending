import logging
from pathlib import Path

from src.models.carousel import CarouselPost

logger = logging.getLogger(__name__)


class CarouselMarkdownExporter:
    def __init__(self, output_dir: str = "outputs/carousel"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def export(self, post: CarouselPost) -> str:
        ts = post.generated_at.strftime("%d/%m/%Y %H:%M")

        lines = [
            f"# 🎠 Carrossel do dia — {post.topic}",
            "",
            f"**Gerado em:** {ts} UTC | **Run:** `{post.run_id or 'manual'}` | "
            f"**Região:** {post.region} | **Melhor horário (BRT):** {post.best_posting_time_brt or 'a definir'}",
            "",
            f"> 🎯 **Gancho (Slide 1):** {post.hook}",
            "",
            "## 🖼️ Slides",
            "",
        ]

        for slide in post.slides:
            lines.append(f"### Slide {slide.number} — {slide.headline}")
            if slide.image_path:
                lines.append(f"![{slide.headline}]({slide.image_path})")
                if slide.image_credit:
                    lines.append(f"*{slide.image_credit}*")
            lines.append(f"{slide.body}")
            if slide.visual_direction:
                lines.append(f"- 🎨 *Direção visual:* {slide.visual_direction}")
            lines.append("")

        lines += [
            "## 📸 Legenda — Instagram",
            "",
            post.caption_instagram,
            "",
            " ".join(post.hashtags_instagram),
            "",
            "## 🎵 Legenda — TikTok",
            "",
            post.caption_tiktok,
            "",
            " ".join(post.hashtags_tiktok),
            "",
            "## 📣 Chamada para ação",
            "",
            post.cta,
            "",
            "## 📚 Fontes",
            "",
        ]

        if post.sources:
            for s in post.sources:
                url_part = f" — {s.url}" if s.url else ""
                lines.append(f"- {s.label}{url_part}")
        else:
            lines.append("*Nenhuma fonte retornada — revisar antes de postar.*")

        body = "\n".join(lines) + "\n"

        timestamp = post.generated_at.strftime("%Y%m%d_%H%M%S")
        filename = f"carousel_{post.topic_slug}_{timestamp}.md"
        filepath = self.output_dir / filename
        filepath.write_text(body, encoding="utf-8")

        latest = self.output_dir / "latest.md"
        latest.write_text(body, encoding="utf-8")

        logger.info(f"Carousel markdown exported: {filepath}")
        return str(filepath)

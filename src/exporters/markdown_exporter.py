import logging
from datetime import datetime
from pathlib import Path

from src.models.trend import TrendIdea, UrgencyLevel

logger = logging.getLogger(__name__)

URGENCY_EMOJI = {
    UrgencyLevel.LOW: "🟢",
    UrgencyLevel.MEDIUM: "🟡",
    UrgencyLevel.HIGH: "🟠",
    UrgencyLevel.CRITICAL: "🔴",
}

FORMAT_EMOJI = {"short": "⚡", "long": "🎬", "both": "🎯"}


class MarkdownExporter:
    def __init__(self, output_dir: str = "outputs/markdown"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def _render_idea(self, idx: int, idea: TrendIdea) -> str:
        urgency_icon = URGENCY_EMOJI.get(idea.urgency, "⚪")
        fmt_icon = FORMAT_EMOJI.get(idea.video_format.value, "🎬")
        ease_bar = "█" * idea.ease + "░" * (10 - idea.ease)

        titles_md = "\n".join(f"  {i+1}. {t}" for i, t in enumerate(idea.titles))
        thumbs_md = "\n".join(f"  {i+1}. {t}" for i, t in enumerate(idea.thumbnails))
        links_md = "\n".join(f"  - {l}" for l in idea.links) if idea.links else "  - N/A"

        return f"""---

## {idx}. {idea.main_topic}

**Subtema:** {idea.subtopic}
**Score:** `{idea.score:.0f}/100` | **Região:** `{idea.region}` | **Fonte:** `{idea.source}`
**Formato:** {fmt_icon} `{idea.video_format.value}` | **Urgência:** {urgency_icon} `{idea.urgency.value}` | **Facilidade:** `{ease_bar}` {idea.ease}/10

### Por que está em alta
{idea.why_trending}

### Gancho
> {idea.hook}

### Títulos sugeridos
{titles_md}

### Thumbnails
{thumbs_md}

### Links de referência
{links_md}
"""

    def export(self, ideas: list[TrendIdea], run_id: str = "") -> str:
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        filename = f"trends_{timestamp}.md"
        if run_id:
            filename = f"trends_{run_id}_{timestamp}.md"

        header = f"""# Tendências de Conteúdo — {datetime.utcnow().strftime("%d/%m/%Y %H:%M")} UTC

**Total de ideias:** {len(ideas)} | **Run ID:** `{run_id or "manual"}`

> Gerado automaticamente pelo AI Trends Research Agent

"""
        body = "\n".join(self._render_idea(i + 1, idea) for i, idea in enumerate(ideas))
        content = header + body

        filepath = self.output_dir / filename
        filepath.write_text(content, encoding="utf-8")

        latest = self.output_dir / "latest.md"
        latest.write_text(content, encoding="utf-8")

        logger.info(f"Markdown exported to: {filepath}")
        return str(filepath)

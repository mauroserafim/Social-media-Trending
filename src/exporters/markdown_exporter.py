import logging
from datetime import datetime
from pathlib import Path

from src.models.trend import CrossPlatformTrend, NicheIdea, TrendReport, TrendSection, UrgencyLevel

logger = logging.getLogger(__name__)

URGENCY_EMOJI = {
    UrgencyLevel.LOW: "🟢",
    UrgencyLevel.MEDIUM: "🟡",
    UrgencyLevel.HIGH: "🟠",
    UrgencyLevel.CRITICAL: "🔴",
}

FORMAT_EMOJI = {"short": "⚡", "long": "🎬", "both": "🎯"}
DIVIDER = "\n---\n"


class MarkdownExporter:
    def __init__(self, output_dir: str = "outputs/markdown"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def _render_section(self, section: TrendSection) -> str:
        lines = [f"\n#### {section.emoji} {section.label} — Top {len(section.trends)}\n"]
        for i, t in enumerate(section.trends, 1):
            url_part = f" · [{t.url}]({t.url})" if t.url else ""
            lines.append(f"{i:>2}. {t.title}{url_part}")
        return "\n".join(lines)

    def _render_region_block(self, title: str, sections: list[TrendSection]) -> str:
        if not sections:
            return f"\n### {title}\n\n*Nenhum dado coletado.*\n"
        parts = [f"\n### {title}\n"]
        for section in sections:
            parts.append(self._render_section(section))
        return "\n".join(parts)

    def _render_connections(self, label: str, icon: str, connections: list[CrossPlatformTrend], desc: str) -> str:
        if not connections:
            return f"\n### {icon} {label}\n\n*Nenhum tema encontrado.*\n"
        lines = [
            f"\n### {icon} {label}\n",
            f"_{desc}_\n",
        ]
        for i, cp in enumerate(connections, 1):
            platforms_str = " + ".join(cp.platforms)
            lines.append(f"{i:>2}. **{cp.topic}** `[{cp.count}x]` — _{platforms_str}_")
            if cp.sample_titles:
                lines.append(f"     > ex: _{cp.sample_titles[0]}_")
        return "\n".join(lines)

    def _render_niche_table(self, ideas: list[NicheIdea]) -> str:
        if not ideas:
            return "\n### 🎯 MEU NICHO\n\n*Nenhuma ideia gerada. Verifique OPENAI_API_KEY e os logs.*\n"

        lines = [
            f"\n### 🎯 MEU NICHO — Mecanismo Americano — Top {len(ideas)}\n",
            "| # | Título | Subtema | Por que está em alta |",
            "|---|--------|---------|----------------------|",
        ]
        for i, idea in enumerate(ideas, 1):
            urgency = URGENCY_EMOJI.get(idea.urgency, "⚪")
            fmt = FORMAT_EMOJI.get(idea.video_format.value, "🎬")
            why = idea.why_trending.replace("|", "·")[:120]
            lines.append(
                f"| {i} {urgency} {fmt} | **{idea.main_topic}** | {idea.subtopic} | {why} |"
            )
        return "\n".join(lines)

    def export(self, report: TrendReport) -> str:
        ts = report.generated_at.strftime("%d/%m/%Y %H:%M")
        run = report.run_id or "manual"

        total_br = sum(len(s.trends) for s in report.sections_br)
        total_us = sum(len(s.trends) for s in report.sections_us)

        header = (
            f"# 📊 Tendências em Alta — {ts} UTC\n\n"
            f"**Run:** `{run}` | "
            f"**BR:** {total_br} trends | "
            f"**US:** {total_us} trends | "
            f"**Cross-platform:** {len(report.cross_platform)} | "
            f"**BR+US:** {len(report.br_us_connections)} | "
            f"**Nicho:** {len(report.niche_ideas)} ideias\n"
        )

        body = "\n".join([
            header,
            DIVIDER,
            self._render_region_block("🌍 BRASIL — Tendências Gerais", report.sections_br),
            DIVIDER,
            self._render_region_block("🇺🇸 EUA — Tendências Gerais", report.sections_us),
            DIVIDER,
            self._render_connections(
                "BR + EUA — Temas Conectados",
                "🔗",
                report.br_us_connections,
                "temas que aparecem tanto em fontes brasileiras quanto americanas (ex: caso Ramagem, política BR com repercussão nos EUA)"
            ),
            DIVIDER,
            self._render_connections(
                "CROSS-PLATFORM — Trending em múltiplas fontes",
                "🔥",
                report.cross_platform,
                "temas em 2+ plataformas simultaneamente — sinal mais forte"
            ),
            DIVIDER,
            self._render_niche_table(report.niche_ideas),
        ])

        timestamp = report.generated_at.strftime("%Y%m%d_%H%M%S")
        filename = f"trends_{run}_{timestamp}.md"
        filepath = self.output_dir / filename
        filepath.write_text(body, encoding="utf-8")

        latest = self.output_dir / "latest.md"
        latest.write_text(body, encoding="utf-8")

        logger.info(f"Markdown exported: {filepath}")
        return str(filepath)

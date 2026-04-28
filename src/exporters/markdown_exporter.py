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

    def _render_cross_platform(self, cross: list[CrossPlatformTrend]) -> str:
        if not cross:
            return "\n### 🔥 CROSS-PLATFORM\n\n*Nenhum tema cruzado encontrado.*\n"

        lines = [
            "\n### 🔥 CROSS-PLATFORM — Trending em múltiplas fontes\n",
            "*(temas que aparecem simultaneamente em 2+ plataformas — sinal mais forte)*\n",
        ]
        for i, cp in enumerate(cross, 1):
            platforms_str = " + ".join(cp.platforms)
            badge = f"`{cp.count}x`"
            lines.append(f"{i:>2}. {badge} **{cp.topic}** — _{platforms_str}_")
            if cp.sample_titles:
                lines.append(f"     > ex: _{cp.sample_titles[0]}_")
        return "\n".join(lines)

    def _render_niche(self, ideas: list[NicheIdea]) -> str:
        if not ideas:
            return "\n### 🎯 MEU NICHO\n\n*Nenhuma ideia gerada. Verifique a OPENAI_API_KEY e os logs.*\n"

        lines = [f"\n### 🎯 MEU NICHO — Mecanismo Americano — Top {len(ideas)}\n"]

        for i, idea in enumerate(ideas, 1):
            urgency_icon = URGENCY_EMOJI.get(idea.urgency, "⚪")
            fmt_icon = FORMAT_EMOJI.get(idea.video_format.value, "🎬")
            platforms_str = " · ".join(idea.platforms) if idea.platforms else idea.source

            lines.append(f"#### {i}. {idea.main_topic}")
            lines.append(
                f"**Subtema:** {idea.subtopic}  \n"
                f"**Região:** `{idea.region}` | "
                f"**Formato:** {fmt_icon} `{idea.video_format.value}` | "
                f"**Urgência:** {urgency_icon} `{idea.urgency.value}` | "
                f"**Facilidade:** `{idea.ease}/10`  \n"
                f"**Fontes:** _{platforms_str}_\n"
            )
            lines.append(f"**Por que está em alta:** {idea.why_trending}\n")
            lines.append(f"**Ângulo para o canal:** {idea.niche_angle}\n")
            if idea.links:
                link_parts = " · ".join(f"[link]({lk})" for lk in idea.links[:3])
                lines.append(f"**Referências:** {link_parts}\n")
            lines.append("---")

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
            f"**Cross-platform:** {len(report.cross_platform)} tópicos | "
            f"**Nicho:** {len(report.niche_ideas)} ideias\n"
        )

        body = "\n".join([
            header,
            DIVIDER,
            self._render_region_block("🌍 BRASIL — Tendências Gerais", report.sections_br),
            DIVIDER,
            self._render_region_block("🇺🇸 EUA — Tendências Gerais", report.sections_us),
            DIVIDER,
            self._render_cross_platform(report.cross_platform),
            DIVIDER,
            self._render_niche(report.niche_ideas),
        ])

        timestamp = report.generated_at.strftime("%Y%m%d_%H%M%S")
        filename = f"trends_{run}_{timestamp}.md"
        filepath = self.output_dir / filename
        filepath.write_text(body, encoding="utf-8")

        latest = self.output_dir / "latest.md"
        latest.write_text(body, encoding="utf-8")

        logger.info(f"Markdown exported: {filepath}")
        return str(filepath)

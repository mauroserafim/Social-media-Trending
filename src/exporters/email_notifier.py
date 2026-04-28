import logging
import os
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from src.models.trend import TrendReport, UrgencyLevel

logger = logging.getLogger(__name__)

URGENCY_COLOR = {
    UrgencyLevel.LOW: "#27ae60",
    UrgencyLevel.MEDIUM: "#f39c12",
    UrgencyLevel.HIGH: "#e67e22",
    UrgencyLevel.CRITICAL: "#e74c3c",
}

FORMAT_LABEL = {"short": "⚡ Short", "long": "🎬 Long", "both": "🎯 Short + Long"}


def _build_html(report: TrendReport) -> str:
    now = report.generated_at.strftime("%d/%m/%Y %H:%M UTC")
    run = report.run_id or "manual"

    # Cross-platform section
    cross_rows = ""
    for i, cp in enumerate(report.cross_platform[:8], 1):
        platforms = " + ".join(cp.platforms)
        cross_rows += (
            f"<tr>"
            f"<td style='padding:6px 8px;color:#666;font-size:13px;'>{i}.</td>"
            f"<td style='padding:6px 8px;font-weight:bold;'>{cp.topic}</td>"
            f"<td style='padding:6px 8px;'><span style='background:#e8f4f8;border-radius:12px;"
            f"padding:2px 8px;font-size:12px;'>{cp.count}x</span></td>"
            f"<td style='padding:6px 8px;color:#888;font-size:12px;'>{platforms}</td>"
            f"</tr>"
        )

    # Niche ideas cards
    niche_cards = ""
    for i, idea in enumerate(report.niche_ideas, 1):
        color = URGENCY_COLOR.get(idea.urgency, "#95a5a6")
        fmt = FORMAT_LABEL.get(idea.video_format.value, idea.video_format.value)
        platforms_str = " · ".join(idea.platforms) if idea.platforms else idea.source
        niche_cards += f"""
        <div style="border:1px solid #e0e0e0;border-radius:8px;margin-bottom:16px;overflow:hidden;">
          <div style="background:{color};color:white;padding:10px 16px;display:flex;justify-content:space-between;align-items:center;">
            <strong>#{i} {idea.main_topic}</strong>
            <span style="font-size:12px;opacity:.85;">{idea.urgency.value.upper()} · {fmt}</span>
          </div>
          <div style="padding:14px 16px;">
            <p style="color:#555;margin:0 0 6px;font-size:13px;">
              <strong>Subtema:</strong> {idea.subtopic} &nbsp;|&nbsp;
              <strong>Região:</strong> {idea.region} &nbsp;|&nbsp;
              <strong>Facilidade:</strong> {idea.ease}/10
            </p>
            <p style="color:#777;margin:0 0 6px;font-size:12px;"><em>Fontes: {platforms_str}</em></p>
            <p style="margin:8px 0 4px;font-size:13px;color:#333;"><strong>Por que está em alta:</strong> {idea.why_trending}</p>
            <p style="margin:4px 0;font-size:13px;color:#333;"><strong>Ângulo para o canal:</strong> {idea.niche_angle}</p>
          </div>
        </div>"""

    # Per-region trend tables (top 5 per platform)
    def render_region_table(label: str, sections) -> str:
        if not sections:
            return ""
        html = f"<h3 style='color:#444;margin:20px 0 10px;'>{label}</h3>"
        for section in sections:
            html += f"<p style='margin:12px 0 4px;font-weight:bold;color:#555;'>{section.emoji} {section.label}</p><ol style='margin:0;padding-left:20px;'>"
            for t in section.trends[:5]:
                url_part = f" <a href='{t.url}' style='color:#aaa;font-size:11px;'>[link]</a>" if t.url else ""
                html += f"<li style='font-size:13px;margin-bottom:2px;'>{t.title}{url_part}</li>"
            html += "</ol>"
        return html

    br_html = render_region_table("🌍 Brasil", report.sections_br)
    us_html = render_region_table("🇺🇸 EUA", report.sections_us)

    return f"""<!DOCTYPE html>
<html>
<body style="font-family:Arial,sans-serif;max-width:700px;margin:0 auto;padding:20px;color:#222;">
  <div style="background:linear-gradient(135deg,#1a1a2e,#16213e);color:white;padding:24px;border-radius:10px;margin-bottom:24px;">
    <h1 style="margin:0;font-size:22px;">📊 Tendências em Alta</h1>
    <p style="margin:6px 0 0;opacity:.8;font-size:14px;">{now} &nbsp;·&nbsp; Run {run}</p>
    <p style="margin:4px 0 0;opacity:.7;font-size:13px;">
      {sum(len(s.trends) for s in report.sections_br)} trends BR &nbsp;·&nbsp;
      {sum(len(s.trends) for s in report.sections_us)} trends US &nbsp;·&nbsp;
      {len(report.cross_platform)} cross-platform &nbsp;·&nbsp;
      {len(report.niche_ideas)} ideias de nicho
    </p>
  </div>

  {br_html}
  {us_html}

  <h2 style="color:#e74c3c;margin:24px 0 12px;">🔥 Cross-Platform</h2>
  <table style="width:100%;border-collapse:collapse;margin-bottom:24px;">
    <thead><tr style="background:#f5f5f5;">
      <th style="padding:6px 8px;text-align:left;font-size:13px;">#</th>
      <th style="padding:6px 8px;text-align:left;font-size:13px;">Tema</th>
      <th style="padding:6px 8px;text-align:left;font-size:13px;">Plataformas</th>
      <th style="padding:6px 8px;text-align:left;font-size:13px;">Onde</th>
    </tr></thead>
    <tbody>{cross_rows}</tbody>
  </table>

  <h2 style="color:#764ba2;margin:24px 0 12px;">🎯 Meu Nicho — Mecanismo Americano</h2>
  {niche_cards}

  <p style="color:#aaa;font-size:12px;text-align:center;margin-top:24px;">
    AI Trends Research Agent · GitHub Actions
  </p>
</body>
</html>"""


def _build_plain(report: TrendReport) -> str:
    now = report.generated_at.strftime("%d/%m/%Y %H:%M UTC")
    run = report.run_id or "manual"
    lines = [f"TENDÊNCIAS EM ALTA — {now}", f"Run ID: {run}", "=" * 60, ""]

    for region_label, sections in [("BRASIL", report.sections_br), ("EUA", report.sections_us)]:
        lines.append(f"--- {region_label} ---")
        for section in sections:
            lines.append(f"\n{section.emoji} {section.label}")
            for i, t in enumerate(section.trends[:5], 1):
                lines.append(f"  {i}. {t.title}")
        lines.append("")

    lines.append("--- CROSS-PLATFORM ---")
    for i, cp in enumerate(report.cross_platform[:8], 1):
        lines.append(f"  {i}. [{cp.count}x] {cp.topic} — {' + '.join(cp.platforms)}")
    lines.append("")

    lines.append("--- MEU NICHO ---")
    for i, idea in enumerate(report.niche_ideas, 1):
        lines.append(f"\n{i}. {idea.main_topic}")
        lines.append(f"   Subtema: {idea.subtopic}")
        lines.append(f"   Urgência: {idea.urgency.value} | Formato: {idea.video_format.value} | Facilidade: {idea.ease}/10")
        lines.append(f"   Por que: {idea.why_trending}")
        lines.append(f"   Ângulo: {idea.niche_angle}")

    return "\n".join(lines)


class EmailNotifier:
    def __init__(self):
        self.smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
        self.smtp_port = int(os.getenv("SMTP_PORT", "587"))
        self.smtp_user = os.getenv("SMTP_USER", "")
        self.smtp_password = os.getenv("SMTP_PASSWORD", "")
        self.from_addr = os.getenv("EMAIL_FROM", self.smtp_user)
        self.to_addrs = [a.strip() for a in os.getenv("EMAIL_TO", "").split(",") if a.strip()]

    def is_configured(self) -> bool:
        return bool(self.smtp_user and self.smtp_password and self.to_addrs)

    def send(self, report: TrendReport) -> bool:
        if not self.is_configured():
            logger.warning("Email not configured — skipping notification")
            return False

        now = report.generated_at.strftime("%d/%m %H:%M")
        subject = (
            f"📊 Tendências {now} UTC — "
            f"{len(report.niche_ideas)} nicho · "
            f"{len(report.cross_platform)} cross-platform"
        )

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = self.from_addr
        msg["To"] = ", ".join(self.to_addrs)
        msg.attach(MIMEText(_build_plain(report), "plain", "utf-8"))
        msg.attach(MIMEText(_build_html(report), "html", "utf-8"))

        try:
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.ehlo()
                server.starttls()
                server.login(self.smtp_user, self.smtp_password)
                server.sendmail(self.from_addr, self.to_addrs, msg.as_bytes())
            logger.info(f"Email sent to: {', '.join(self.to_addrs)}")
            return True
        except Exception as e:
            logger.error(f"Email sending failed: {e}")
            return False

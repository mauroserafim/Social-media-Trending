import logging
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from src.models.trend import TrendReport, TrendSection, UrgencyLevel

logger = logging.getLogger(__name__)

URGENCY_COLOR = {
    UrgencyLevel.LOW: "#27ae60",
    UrgencyLevel.MEDIUM: "#f39c12",
    UrgencyLevel.HIGH: "#e67e22",
    UrgencyLevel.CRITICAL: "#e74c3c",
}

URGENCY_EMOJI = {
    UrgencyLevel.LOW: "🟢",
    UrgencyLevel.MEDIUM: "🟡",
    UrgencyLevel.HIGH: "🟠",
    UrgencyLevel.CRITICAL: "🔴",
}

FORMAT_LABEL = {"short": "⚡ Short", "long": "🎬 Long", "both": "🎯 Short+Long"}

PLATFORM_CONFIG = [
    ("youtube",       "📺", "YouTube"),
    ("news",          "📰", "Notícias"),
    ("google_trends", "📊", "Google Trends"),
    ("reddit",        "💬", "Reddit"),
    ("tiktok",        "🎵", "TikTok"),
]


def _col_html(section: TrendSection | None) -> str:
    if not section:
        return "<p style='color:#aaa;font-size:12px;font-style:italic;'>Sem dados</p>"
    html = "<ol style='margin:0;padding-left:18px;'>"
    for t in section.trends[:10]:
        url_part = f" <a href='{t.url}' style='color:#888;font-size:10px;'>[→]</a>" if t.url else ""
        html += f"<li style='font-size:12px;margin-bottom:4px;color:#222;line-height:1.4;'>{t.title}{url_part}</li>"
    html += "</ol>"
    return html


def _platform_block(emoji: str, label: str, br_section: TrendSection | None, us_section: TrendSection | None) -> str:
    if not br_section and not us_section:
        return ""
    return f"""
<div style="margin-bottom:24px;">
  <h3 style="margin:0 0 10px;font-size:15px;color:#1a1a2e;border-bottom:2px solid #1a1a2e;padding-bottom:6px;">
    {emoji} {label}
  </h3>
  <table style="width:100%;border-collapse:collapse;">
    <tr>
      <th style="width:50%;padding:6px 10px;background:#f0f4ff;font-size:12px;color:#333;text-align:left;border-radius:4px 0 0 0;">
        🌍 Brasil
      </th>
      <th style="width:50%;padding:6px 10px;background:#fff4f0;font-size:12px;color:#333;text-align:left;border-radius:0 4px 0 0;border-left:3px solid white;">
        🇺🇸 EUA
      </th>
    </tr>
    <tr>
      <td style="padding:10px;vertical-align:top;background:#f8faff;border:1px solid #e8eaf0;">
        {_col_html(br_section)}
      </td>
      <td style="padding:10px;vertical-align:top;background:#fffaf8;border:1px solid #f0e8e0;border-left:3px solid white;">
        {_col_html(us_section)}
      </td>
    </tr>
  </table>
</div>"""


def _niche_table_html(ideas) -> str:
    if not ideas:
        return "<p style='color:#999;'>Nenhuma ideia gerada.</p>"
    rows = ""
    for i, idea in enumerate(ideas, 1):
        urgency_icon = URGENCY_EMOJI.get(idea.urgency, "⚪")
        fmt = FORMAT_LABEL.get(idea.video_format.value, idea.video_format.value)
        why = idea.why_trending[:150] + ("…" if len(idea.why_trending) > 150 else "")
        rows += (
            f"<tr style='border-bottom:1px solid #eee;'>"
            f"<td style='padding:8px;font-size:12px;color:#888;vertical-align:top;'>{i} {urgency_icon}</td>"
            f"<td style='padding:8px;vertical-align:top;'>"
            f"<strong style='font-size:13px;'>{idea.main_topic}</strong>"
            f"<br><span style='font-size:11px;color:#888;'>{fmt} · {idea.region} · Facilidade {idea.ease}/10</span>"
            f"</td>"
            f"<td style='padding:8px;font-size:12px;color:#555;vertical-align:top;'>{idea.subtopic}</td>"
            f"<td style='padding:8px;font-size:12px;color:#555;vertical-align:top;'>{why}</td>"
            f"</tr>"
        )
    return (
        f"<table style='width:100%;border-collapse:collapse;'>"
        f"<thead><tr style='background:#1a1a2e;color:white;'>"
        f"<th style='padding:8px;text-align:left;font-size:12px;'>#</th>"
        f"<th style='padding:8px;text-align:left;font-size:12px;'>Título</th>"
        f"<th style='padding:8px;text-align:left;font-size:12px;'>Subtema</th>"
        f"<th style='padding:8px;text-align:left;font-size:12px;'>Por que está em alta</th>"
        f"</tr></thead><tbody>{rows}</tbody></table>"
    )


def _build_html(report: TrendReport) -> str:
    now = report.generated_at.strftime("%d/%m/%Y %H:%M UTC")
    run = report.run_id or "manual"
    total_br = sum(len(s.trends) for s in report.sections_br)
    total_us = sum(len(s.trends) for s in report.sections_us)

    # Index sections by platform for quick lookup
    br_by_platform = {s.platform: s for s in report.sections_br}
    us_by_platform = {s.platform: s for s in report.sections_us}

    platform_blocks = ""
    for platform, emoji, label in PLATFORM_CONFIG:
        platform_blocks += _platform_block(
            emoji, label,
            br_by_platform.get(platform),
            us_by_platform.get(platform),
        )

    return f"""<!DOCTYPE html>
<html>
<body style="font-family:Arial,sans-serif;max-width:820px;margin:0 auto;padding:20px;color:#222;">

  <div style="background:linear-gradient(135deg,#1a1a2e,#16213e);color:white;padding:24px;border-radius:10px;margin-bottom:28px;">
    <h1 style="margin:0;font-size:22px;">📊 Tendências em Alta</h1>
    <p style="margin:6px 0 0;opacity:.8;font-size:14px;">{now} · Run {run}</p>
    <p style="margin:4px 0 0;opacity:.7;font-size:12px;">
      BR: {total_br} trends &nbsp;·&nbsp; US: {total_us} trends &nbsp;·&nbsp; Nicho: {len(report.niche_ideas)} ideias
    </p>
  </div>

  {platform_blocks}

  <hr style="border:none;border-top:2px solid #1a1a2e;margin:28px 0;">

  <h3 style="color:#1a1a2e;margin:0 0 12px;font-size:16px;">🎯 Meu Nicho — Mecanismo Americano</h3>
  {_niche_table_html(report.niche_ideas)}

  <p style="color:#bbb;font-size:11px;text-align:center;margin-top:24px;">
    AI Trends Research Agent · GitHub Actions
  </p>
</body>
</html>"""


def _build_plain(report: TrendReport) -> str:
    now = report.generated_at.strftime("%d/%m/%Y %H:%M UTC")
    run = report.run_id or "manual"
    lines = [f"TENDÊNCIAS EM ALTA — {now}", f"Run: {run}", "=" * 60, ""]

    br_by_platform = {s.platform: s for s in report.sections_br}
    us_by_platform = {s.platform: s for s in report.sections_us}

    for platform, emoji, label in PLATFORM_CONFIG:
        br = br_by_platform.get(platform)
        us = us_by_platform.get(platform)
        if not br and not us:
            continue
        lines.append(f"\n{emoji} {label.upper()}")
        lines.append(f"{'BRASIL':<40} {'EUA'}")
        lines.append("-" * 80)
        br_items = [t.title[:38] for t in br.trends[:10]] if br else []
        us_items = [t.title[:38] for t in us.trends[:10]] if us else []
        for i in range(max(len(br_items), len(us_items))):
            b = br_items[i] if i < len(br_items) else ""
            u = us_items[i] if i < len(us_items) else ""
            lines.append(f"{i+1:>2}. {b:<38} {u}")
        lines.append("")

    lines.append("\n--- MEU NICHO ---")
    lines.append(f"{'#':<3} {'TÍTULO':<30} {'SUBTEMA':<25} POR QUE ESTÁ EM ALTA")
    lines.append("-" * 100)
    for i, idea in enumerate(report.niche_ideas, 1):
        why = idea.why_trending[:55] + "…" if len(idea.why_trending) > 55 else idea.why_trending
        lines.append(f"{i:<3} {idea.main_topic:<30} {idea.subtopic:<25} {why}")

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
        subject = f"📊 Tendências {now} UTC — {len(report.niche_ideas)} ideias de nicho"

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

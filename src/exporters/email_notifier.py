import logging
import os
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

from src.models.trend import TrendIdea, UrgencyLevel

logger = logging.getLogger(__name__)

URGENCY_COLOR = {
    UrgencyLevel.LOW: "#27ae60",
    UrgencyLevel.MEDIUM: "#f39c12",
    UrgencyLevel.HIGH: "#e67e22",
    UrgencyLevel.CRITICAL: "#e74c3c",
}

FORMAT_LABEL = {"short": "⚡ Short", "long": "🎬 Long", "both": "🎯 Short + Long"}


def _build_html(ideas: list[TrendIdea], run_id: str) -> str:
    now = datetime.utcnow().strftime("%d/%m/%Y %H:%M UTC")

    cards = ""
    for i, idea in enumerate(ideas, 1):
        color = URGENCY_COLOR.get(idea.urgency, "#95a5a6")
        fmt = FORMAT_LABEL.get(idea.video_format.value, idea.video_format.value)
        titles_html = "".join(f"<li>{t}</li>" for t in idea.titles)
        cards += f"""
        <div style="border:1px solid #e0e0e0;border-radius:8px;margin-bottom:20px;overflow:hidden;">
          <div style="background:{color};color:white;padding:12px 16px;display:flex;justify-content:space-between;align-items:center;">
            <strong>#{i} {idea.main_topic}</strong>
            <span style="background:rgba(0,0,0,0.2);border-radius:20px;padding:2px 10px;font-size:13px;">Score {idea.score:.0f}/100</span>
          </div>
          <div style="padding:16px;">
            <p style="color:#666;margin:0 0 8px;font-size:13px;"><strong>Subtema:</strong> {idea.subtopic} &nbsp;|&nbsp; <strong>Região:</strong> {idea.region} &nbsp;|&nbsp; <strong>Formato:</strong> {fmt} &nbsp;|&nbsp; <strong>Facilidade:</strong> {idea.ease}/10</p>
            <p style="background:#f8f9fa;border-left:3px solid {color};padding:10px;margin:10px 0;font-style:italic;">"{idea.hook}"</p>
            <p style="margin:4px 0;font-size:13px;color:#555;">{idea.why_trending}</p>
            <p style="margin:12px 0 4px;"><strong>Títulos sugeridos:</strong></p>
            <ol style="margin:0;padding-left:20px;font-size:13px;color:#333;">{titles_html}</ol>
          </div>
        </div>"""

    return f"""<!DOCTYPE html>
<html>
<body style="font-family:Arial,sans-serif;max-width:680px;margin:0 auto;padding:20px;color:#222;">
  <div style="background:linear-gradient(135deg,#667eea,#764ba2);color:white;padding:24px;border-radius:10px;margin-bottom:24px;">
    <h1 style="margin:0;font-size:22px;">📊 Tendências de Conteúdo</h1>
    <p style="margin:6px 0 0;opacity:.85;font-size:14px;">{now} &nbsp;·&nbsp; {len(ideas)} ideias geradas &nbsp;·&nbsp; Run {run_id}</p>
  </div>
  {cards}
  <p style="color:#aaa;font-size:12px;text-align:center;margin-top:24px;">
    AI Trends Research Agent · GitHub Actions · Próxima execução em ~4h
  </p>
</body>
</html>"""


def _build_plain(ideas: list[TrendIdea], run_id: str) -> str:
    now = datetime.utcnow().strftime("%d/%m/%Y %H:%M UTC")
    lines = [f"TENDÊNCIAS DE CONTEÚDO — {now}", f"Run ID: {run_id}", "=" * 60, ""]
    for i, idea in enumerate(ideas, 1):
        lines.append(f"{i}. [{idea.score:.0f}/100] {idea.main_topic}")
        lines.append(f"   Subtema: {idea.subtopic}")
        lines.append(f"   Urgência: {idea.urgency.value} | Formato: {idea.video_format.value} | Facilidade: {idea.ease}/10")
        lines.append(f"   Gancho: {idea.hook}")
        lines.append(f"   Por que: {idea.why_trending}")
        lines.append(f"   Títulos:")
        for t in idea.titles:
            lines.append(f"     - {t}")
        lines.append("")
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

    def send(self, ideas: list[TrendIdea], run_id: str = "") -> bool:
        if not self.is_configured():
            logger.warning("Email not configured — skipping notification")
            return False

        if not ideas:
            logger.info("No ideas to send via email")
            return False

        subject = f"📊 {len(ideas)} tendências de conteúdo — {datetime.utcnow().strftime('%d/%m %H:%M')} UTC"

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = self.from_addr
        msg["To"] = ", ".join(self.to_addrs)
        msg.attach(MIMEText(_build_plain(ideas, run_id), "plain", "utf-8"))
        msg.attach(MIMEText(_build_html(ideas, run_id), "html", "utf-8"))

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

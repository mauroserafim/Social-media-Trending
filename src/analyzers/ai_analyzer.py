import json
import logging
import os
from typing import Optional

from openai import OpenAI

from src.models.trend import RawTrend, TrendIdea, UrgencyLevel, VideoFormat

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """Você é um estrategista de conteúdo digital especializado em criar vídeos virais.
Analisa tendências do Brasil e dos EUA e gera ideias de conteúdo altamente otimizadas.
Sempre responde em JSON válido, sem markdown, sem texto extra."""

IDEA_PROMPT = """Analise as tendências abaixo e gere ideias de conteúdo para criadores de vídeo.

TENDÊNCIAS:
{trends_json}

Para cada tendência relevante, gere um objeto JSON com esta estrutura exata:
{{
  "main_topic": "tema principal em português",
  "subtopic": "subtema específico",
  "score": 0-100,
  "why_trending": "por que está em alta agora (2-3 frases)",
  "hook": "gancho inicial irresistível para o vídeo",
  "titles": ["título 1", "título 2", "título 3"],
  "thumbnails": ["descrição thumbnail 1", "descrição thumbnail 2", "descrição thumbnail 3"],
  "video_format": "short|long|both",
  "urgency": "low|medium|high|critical",
  "ease": 1-10,
  "source": "fonte principal",
  "region": "BR|US|GLOBAL",
  "links": ["url1", "url2"]
}}

Retorne um array JSON com até {max_ideas} ideias, ordenadas por score decrescente.
Foque em temas com maior potencial viral para criadores de conteúdo brasileiros."""


class AIAnalyzer:
    def __init__(self, api_key: Optional[str] = None, model: str = "gpt-4o-mini"):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY", "")
        self.model = model
        self._client: Optional[OpenAI] = None

    @property
    def client(self) -> OpenAI:
        if self._client is None:
            if not self.api_key:
                raise ValueError("OPENAI_API_KEY not set")
            self._client = OpenAI(api_key=self.api_key)
        return self._client

    def _build_prompt(self, trends: list[RawTrend], max_ideas: int) -> str:
        trends_data = [
            {
                "title": t.title,
                "source": t.source,
                "region": t.region,
                "score": t.raw_score,
                "url": t.url,
                "views": t.views,
                "views_per_hour": t.views_per_hour,
                "keywords": t.keywords[:5],
            }
            for t in trends
        ]
        return IDEA_PROMPT.format(
            trends_json=json.dumps(trends_data, ensure_ascii=False, indent=2),
            max_ideas=max_ideas,
        )

    def analyze(self, trends: list[RawTrend], max_ideas: int = 10) -> list[TrendIdea]:
        if not trends:
            logger.warning("No trends to analyze")
            return []

        top_trends = sorted(trends, key=lambda t: t.raw_score, reverse=True)[:30]
        prompt = self._build_prompt(top_trends, max_ideas)

        logger.info(f"Sending {len(top_trends)} trends to AI for analysis...")
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.7,
                max_tokens=4000,
                response_format={"type": "json_object"},
            )
            raw = response.choices[0].message.content
            data = json.loads(raw)

            # Handle both {"ideas": [...]} and [...] responses
            if isinstance(data, dict):
                items = data.get("ideas", data.get("trends", list(data.values())[0] if data else []))
            else:
                items = data

            ideas = []
            for item in items:
                try:
                    idea = TrendIdea(
                        main_topic=item["main_topic"],
                        subtopic=item.get("subtopic", ""),
                        score=float(item.get("score", 50)),
                        why_trending=item.get("why_trending", ""),
                        hook=item.get("hook", ""),
                        titles=item.get("titles", ["", "", ""])[:3],
                        thumbnails=item.get("thumbnails", ["", "", ""])[:3],
                        video_format=VideoFormat(item.get("video_format", "both")),
                        urgency=UrgencyLevel(item.get("urgency", "medium")),
                        ease=int(item.get("ease", 5)),
                        source=item.get("source", "mixed"),
                        region=item.get("region", "GLOBAL"),
                        links=item.get("links", [])[:5],
                    )
                    ideas.append(idea)
                except Exception as e:
                    logger.warning(f"Skipping malformed idea: {e}")

            ideas.sort(key=lambda x: x.score, reverse=True)
            logger.info(f"AI generated {len(ideas)} trend ideas")
            return ideas

        except Exception as e:
            logger.error(f"AI analysis failed: {e}")
            return []

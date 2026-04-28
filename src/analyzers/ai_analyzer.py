import json
import logging
import os
from typing import Optional

from openai import OpenAI

from src.models.trend import CrossPlatformTrend, NicheIdea, RawTrend, UrgencyLevel, VideoFormat

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """Você é um estrategista de conteúdo sênior especializado no canal "Mecanismo Americano" — canal brasileiro sobre vida real nos EUA, com público de brasileiros que moram nos EUA e brasileiros no Brasil curiosos sobre a vida americana.

Tom do canal: sem filtro, sem romantizar, realidade crua e prática.
Temas centrais: custo de vida americano, moradia, trabalho, imigração, cultura americana x brasileira, preços reais, dicas práticas.

IMPORTANTE: Pense além do óbvio. Qualquer trending topic pode ter um ângulo para o canal. Copa do Mundo nos EUA → "Quanto custa assistir ao vivo?". Eleição americana → "Como isso afeta imigrantes?". Furacão → "Seguro residencial nos EUA: o que cobre?".

Responda sempre em JSON válido, sem markdown, sem texto extra."""

NICHE_PROMPT = """Analise as tendências abaixo coletadas de múltiplas plataformas (YouTube, jornais, Reddit, Google Trends, TikTok) do Brasil e dos EUA.

Seu trabalho: identificar quais dessas tendências têm potencial para o canal "Mecanismo Americano" e criar o ângulo certo para o nicho.

REGRA DE OURO: Não descarte nenhum tema sem pensar na conexão com a vida nos EUA. Qualquer evento grande nos EUA ou no Brasil que afeta brasileiros imigrantes merece aparecer.

TENDÊNCIAS COLETADAS (ordenadas por força do sinal):
{trends_json}

Para cada tendência relevante, gere um objeto JSON:
{{
  "main_topic": "tema principal em português",
  "subtopic": "ângulo específico do tema",
  "why_trending": "por que está em alta agora — 1-2 frases diretas com dados se possível",
  "niche_angle": "como transformar isso em conteúdo para o canal — o ângulo único para brasileiros nos EUA (1-2 frases)",
  "video_format": "short|long|both",
  "urgency": "low|medium|high|critical",
  "ease": 1-10,
  "source": "fonte principal",
  "region": "BR|US|GLOBAL",
  "links": ["url1"],
  "platforms": ["youtube", "reddit", "rss", "google_trends", "tiktok"]
}}

Retorne array JSON com até {max_ideas} ideias, ordenadas por urgência e potencial de visualizações.
Priorize: temas em 2+ plataformas, temas com dados concretos (preços, números, %), eventos que impactam diretamente a vida do imigrante."""


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

    def _build_input(
        self, trends: list[RawTrend], cross: list[CrossPlatformTrend]
    ) -> str:
        items = []

        # Cross-platform trends first — strongest signal
        for cp in cross[:12]:
            items.append({
                "signal_strength": f"{cp.count} plataformas",
                "topic": cp.topic,
                "platforms": cp.platforms,
                "score": cp.score,
                "examples": cp.sample_titles[:3],
            })

        # Top individual trends by score
        top = sorted(trends, key=lambda t: t.raw_score, reverse=True)[:40]
        for t in top:
            items.append({
                "title": t.title,
                "source": t.source,
                "region": t.region,
                "score": t.raw_score,
                "url": t.url,
            })

        return json.dumps(items, ensure_ascii=False, indent=2)

    def analyze_niche(
        self,
        all_trends: list[RawTrend],
        cross_platform: list[CrossPlatformTrend],
        max_ideas: int = 10,
    ) -> list[NicheIdea]:
        if not all_trends and not cross_platform:
            logger.warning("No trends to analyze")
            return []

        trends_json = self._build_input(all_trends, cross_platform)
        prompt = NICHE_PROMPT.format(trends_json=trends_json, max_ideas=max_ideas)

        logger.info("Sending trends to AI for niche analysis...")
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

            if isinstance(data, dict):
                items = data.get("ideas", data.get("trends", list(data.values())[0] if data else []))
            else:
                items = data

            ideas = []
            for item in items:
                try:
                    idea = NicheIdea(
                        main_topic=item["main_topic"],
                        subtopic=item.get("subtopic", ""),
                        why_trending=item.get("why_trending", ""),
                        niche_angle=item.get("niche_angle", ""),
                        video_format=VideoFormat(item.get("video_format", "both")),
                        urgency=UrgencyLevel(item.get("urgency", "medium")),
                        ease=int(item.get("ease", 5)),
                        source=item.get("source", "mixed"),
                        region=item.get("region", "GLOBAL"),
                        links=item.get("links", [])[:5],
                        platforms=item.get("platforms", []),
                    )
                    ideas.append(idea)
                except Exception as e:
                    logger.warning(f"Skipping malformed idea: {e}")

            logger.info(f"AI generated {len(ideas)} niche ideas")
            return ideas

        except Exception as e:
            logger.error(f"AI analysis failed: {e}")
            return []

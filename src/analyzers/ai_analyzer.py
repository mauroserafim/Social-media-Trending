import json
import logging
import os
import time
from typing import Optional

from google import genai
from google.genai import errors, types
from pydantic import BaseModel

from src.models.trend import CrossPlatformTrend, NicheIdea, RawTrend, UrgencyLevel, VideoFormat

logger = logging.getLogger(__name__)


# Response schema for Gemini structured output — constrains generation to
# guaranteed-valid JSON instead of relying on the model to hand-escape
# quotes correctly inside free-text fields (response_mime_type alone let
# malformed JSON through in practice).
class _NicheIdeaSchema(BaseModel):
    main_topic: str
    subtopic: str
    why_trending: str
    niche_angle: str
    video_format: str
    urgency: str
    ease: int
    source: str
    region: str
    links: list[str]
    platforms: list[str]

SYSTEM_PROMPT = """Você é um estrategista de conteúdo sênior especializado no canal "Mecanismo Americano" — canal brasileiro sobre vida real nos EUA, com público de brasileiros que moram nos EUA e brasileiros no Brasil curiosos sobre a vida americana.

Tom do canal: sem filtro, sem romantizar, realidade crua e prática.

NICHOS PRIORITÁRIOS (em ordem de prioridade):
1. Educação — finanças, carreira, estudos, idiomas, tecnologia, DIY ("Como investir", "Aprender inglês", "Como usar IA")
2. Negócios & Dinheiro — empreendedorismo, renda extra, marketing digital, vendas (dropshipping, afiliados, abrir empresa)
3. Entretenimento — humor, memes, desafios, trends, pegadinhas (vídeos engraçados, trends TikTok)
4. Lifestyle — rotina, vida pessoal, família, minimalismo ("Um dia na minha vida", rotina nos EUA)
5. Viagem — turismo, dicas, experiências, intercâmbio ("Quanto custa viajar para NY")
6. Tecnologia — gadgets, apps, IA, reviews (review iPhone, automação)
7. Direito & Legal — leis, imigração, direitos ("Como funciona visto")
8. Economia & Mercado — inflação, salários, custo de vida (comparações de países)
9. Memes & Viral — conteúdo rápido viralizável (áudios virais)
10. Comunidade & Opinião — debates, opiniões pessoais ("O que eu acho sobre…")

TEMAS A IGNORAR COMPLETAMENTE: jogos de videogame, conteúdo infantil/kids, filmes de ficção, músicas/clipes musicais.

IMPORTANTE: Pense além do óbvio. Qualquer trending topic pode ter um ângulo para o canal. Copa do Mundo nos EUA → "Quanto custa assistir ao vivo?". Eleição americana → "Como isso afeta imigrantes?". Furacão → "Seguro residencial nos EUA: o que cobre?".

Responda sempre em JSON válido, sem markdown, sem texto extra."""

NICHE_PROMPT = """Analise as tendências abaixo coletadas de múltiplas plataformas (YouTube, jornais, Reddit, Google Trends, TikTok) do Brasil e dos EUA.

Seu trabalho: identificar quais dessas tendências têm potencial para o canal "Mecanismo Americano" e criar o ângulo certo para o nicho.

REGRA DE OURO: Não descarte nenhum tema sem pensar na conexão com a vida nos EUA. Qualquer evento grande nos EUA ou no Brasil que afeta brasileiros imigrantes merece aparecer.

IGNORE COMPLETAMENTE: jogos de videogame, conteúdo kids/infantil, filmes de ficção/cinema, músicas/clipes/artistas musicais. Esses temas não têm fit com o nicho.

FOQUE NESTES NICHOS: Educação, Negócios & Dinheiro, Entretenimento (humor/trends), Lifestyle, Viagem, Tecnologia, Direito & Legal, Economia & Mercado, Memes & Viral, Comunidade & Opinião.

TENDÊNCIAS COLETADAS (ordenadas por força do sinal):
{trends_json}

Para cada tendência relevante dentro dos nichos acima, gere um objeto JSON:
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
    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        self.api_key = (api_key or os.getenv("GEMINI_API_KEY", "")).strip()
        self.model = model or os.getenv("GEMINI_MODEL", "gemini-3.6-flash")
        self._client: Optional[genai.Client] = None

    @property
    def client(self) -> genai.Client:
        if self._client is None:
            if not self.api_key:
                raise ValueError("GEMINI_API_KEY not set")
            self._client = genai.Client(api_key=self.api_key)
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
        # Two things make a fresh attempt worth retrying instead of giving up:
        # (1) response_schema constrains Gemini toward valid JSON but doesn't
        #     guarantee it — a stray unescaped quote in a free-text field can
        #     still break the parser occasionally.
        # (2) Gemini's API returns transient 503/429s under load ("high
        #     demand") that usually clear within a few seconds.
        max_attempts = 4
        data = None
        for attempt in range(1, max_attempts + 1):
            try:
                response = self.client.models.generate_content(
                    model=self.model,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        system_instruction=SYSTEM_PROMPT,
                        temperature=0.7,
                        max_output_tokens=8192,
                        response_mime_type="application/json",
                        response_schema=list[_NicheIdeaSchema],
                    ),
                )
                data = json.loads(response.text)
                break
            except json.JSONDecodeError as e:
                logger.warning(f"Malformed JSON from Gemini (attempt {attempt}/{max_attempts}): {e}")
                if attempt == max_attempts:
                    logger.error("AI analysis failed: Gemini kept returning malformed JSON")
                    return []
            except errors.APIError as e:
                logger.warning(f"Gemini API error (attempt {attempt}/{max_attempts}): {e}")
                if attempt == max_attempts:
                    logger.error(f"AI analysis failed: Gemini API error: {e}")
                    return []
                time.sleep(3 * attempt)
            except Exception as e:
                logger.error(f"AI analysis failed: {e}")
                return []

        try:
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

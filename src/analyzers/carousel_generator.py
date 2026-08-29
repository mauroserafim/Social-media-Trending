import json
import logging
import os
from typing import Optional

from google import genai
from google.genai import types

from src.models.carousel import CarouselPost, CarouselSlide, Source, slugify

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """Você é redator sênior e "ghostwriter" do perfil "Mecanismo Americano" — PhD com pós-doutorado nos EUA, vivência real na cultura americana e brasileira, especialista em comparar Brasil x Estados Unidos para brasileiros (imigrantes e curiosos no Brasil).

Sua missão: criar o roteiro de um CARROSSEL para Instagram/TikTok que:
1. Choca ou surpreende o brasileiro logo no gancho (slide 1) — sem sensacionalismo vazio, com dado real.
2. Fala a realidade crua dos EUA, sem romantizar "sonho americano" nem demonizar o Brasil — comparação honesta.
3. Tem CREDIBILIDADE: todo dado numérico ou afirmação factual deve vir acompanhado de uma fonte real e verificável (ex: U.S. Census Bureau, Bureau of Labor Statistics, Pew Research Center, IBGE, Banco Mundial, Numbeo, Migration Policy Institute, OCDE, FBI UCR, CDC). NUNCA invente estatística, ano ou fonte — se não tiver certeza do número exato, use uma faixa aproximada e diga "segundo estimativas de [fonte]".
4. Se o tema não permitir dado numérico sólido, baseie o "choque" em um fato cultural/legal real e verificável, citando a fonte (ex: lei, órgão oficial, pesquisa).

Regras de formato:
- Carrossel: 6 a 8 slides. Slide 1 é o gancho (hook) chocante/curioso. Últimos 1-2 slides sempre trazem uma virada, uma lição prática ou uma pergunta para engajamento. Um dos slides do meio deve ser o "slide do dado" com o número/estatística em destaque e a fonte citada.
- Cada slide tem: headline curta (até 8 palavras, linguagem de card, pode usar CAIXA ALTA em 1-2 palavras-chave) + body (1-3 frases, linguagem direta, sem enrolação) + visual_direction (direção de design para quem vai montar a arte: cores, ícone/imagem sugerida, onde colocar o número em destaque) + image_query (2-5 palavras EM INGLÊS, termo de busca objetivo e literal para banco de imagens gratuito, ex: "worried man reading bill", "new york apartment street", "immigration office queue" — nunca em português, nunca abstrato demais).
- Legenda do Instagram: 4-8 linhas, gancho na primeira linha, storytelling breve, CTA (comentar, salvar, seguir), tom de autoridade + proximidade.
- Legenda do TikTok: mais curta e direta, otimizada para o algoritmo, com gancho na primeira linha.
- Hashtags: 8-12 para Instagram (mix de nicho + amplo), 4-6 para TikTok.
- sources: lista de 1-4 fontes reais usadas nos dados/afirmações, com nome da instituição/pesquisa e URL do domínio oficial quando souber (ex: https://www.census.gov, https://www.pewresearch.org, https://www.bls.gov, https://www.ibge.gov.br). Se não souber a URL exata, coloque a URL do domínio institucional, nunca invente um link de artigo específico.

Responda SOMENTE em JSON válido, sem markdown, sem texto fora do JSON."""

USER_PROMPT_TEMPLATE = """Crie o carrossel de hoje com base neste tema em alta:

Tema principal: {main_topic}
Subtema/ângulo: {subtopic}
Por que está em alta: {why_trending}
Ângulo de nicho sugerido: {niche_angle}
Região: {region}

Temas JÁ publicados recentemente (NÃO repita o mesmo ângulo, escolha um ângulo diferente se o tema for parecido):
{used_topics}

Gere um objeto JSON com o schema exato:
{{
  "topic": "título curto do carrossel",
  "hook": "frase de impacto do slide 1",
  "slides": [
    {{"number": 1, "headline": "...", "body": "...", "visual_direction": "...", "image_query": "..."}}
  ],
  "caption_instagram": "...",
  "caption_tiktok": "...",
  "hashtags_instagram": ["#..."],
  "hashtags_tiktok": ["#..."],
  "sources": [{{"label": "Nome da fonte, ano", "url": "https://..."}}],
  "cta": "chamada para ação final",
  "best_posting_time_brt": "ex: 19h-21h BRT"
}}"""


class CarouselGenerator:
    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY", "")
        self.model = model or os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
        self._client: Optional[genai.Client] = None

    @property
    def client(self) -> genai.Client:
        if self._client is None:
            if not self.api_key:
                raise ValueError("GEMINI_API_KEY not set")
            self._client = genai.Client(api_key=self.api_key)
        return self._client

    def generate(
        self,
        main_topic: str,
        subtopic: str = "",
        why_trending: str = "",
        niche_angle: str = "",
        region: str = "US-BR",
        used_topics: Optional[list[str]] = None,
        run_id: str = "",
    ) -> Optional[CarouselPost]:
        used_topics = used_topics or []
        used_block = "\n".join(f"- {t}" for t in used_topics[:30]) or "- (nenhum ainda)"

        prompt = USER_PROMPT_TEMPLATE.format(
            main_topic=main_topic,
            subtopic=subtopic or "livre",
            why_trending=why_trending or "tema evergreen do nicho",
            niche_angle=niche_angle or "comparação Brasil x EUA",
            region=region,
            used_topics=used_block,
        )

        logger.info(f"Generating carousel for topic: {main_topic}")
        try:
            response = self.client.models.generate_content(
                model=self.model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_PROMPT,
                    temperature=0.8,
                    max_output_tokens=3000,
                    response_mime_type="application/json",
                ),
            )
            data = json.loads(response.text)

            slides = [
                CarouselSlide(
                    number=s.get("number", i + 1),
                    headline=s.get("headline", ""),
                    body=s.get("body", ""),
                    visual_direction=s.get("visual_direction", ""),
                    image_query=s.get("image_query", ""),
                )
                for i, s in enumerate(data.get("slides", []))
            ]
            sources = [
                Source(label=s.get("label", ""), url=s.get("url", ""))
                for s in data.get("sources", [])
                if s.get("label")
            ]

            topic = data.get("topic", main_topic)
            post = CarouselPost(
                topic=topic,
                topic_slug=slugify(topic),
                region=region,
                hook=data.get("hook", ""),
                slides=slides,
                caption_instagram=data.get("caption_instagram", ""),
                caption_tiktok=data.get("caption_tiktok", ""),
                hashtags_instagram=data.get("hashtags_instagram", []),
                hashtags_tiktok=data.get("hashtags_tiktok", []),
                sources=sources,
                cta=data.get("cta", ""),
                best_posting_time_brt=data.get("best_posting_time_brt", ""),
                run_id=run_id,
            )
            logger.info(f"Carousel generated: '{post.topic}' with {len(post.slides)} slides")
            return post

        except Exception as e:
            logger.error(f"Carousel generation failed: {e}")
            return None

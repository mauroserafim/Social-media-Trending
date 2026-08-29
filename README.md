# AI Trends Research Agent

Agente automático que varre YouTube, Google Trends e RSS de notícias, identifica temas virais no nicho Brasil × EUA, analisa com IA e gera ideias de vídeos prontas.

## Funcionalidades

- Coleta tendências do YouTube (API oficial), Google Trends e RSS (CNN, Reuters, G1, TechCrunch, etc.)
- Análise com IA via Gemini (`gemini-3.6-flash` por padrão, free tier do Google AI Studio)
- Gera até 10 ideias por execução com: score, gancho, 3 títulos, 3 thumbnails, formato e urgência
- **Gera 1 carrossel completo por dia** para Instagram/TikTok (persona PhD, EUA x Brasil) — ver seção [Carrossel diário](#carrossel-diário-instagramtiktok)
- Exporta em JSON e Markdown
- Armazena histórico em SQLite
- Roda automaticamente via GitHub Actions a cada 4 horas
- API REST opcional (deploy no Render/Railway)

## Configuração rápida

### 1. Clone e configure o ambiente

```bash
git clone https://github.com/mauroserafim/carrocel-social-media-
cd carrocel-social-media-
cp .env.example .env
# Edite .env com suas chaves
pip install -r requirements.txt
```

### 2. Configure as variáveis

Edite `.env`:

```env
GEMINI_API_KEY=...           # Obrigatório — grátis em aistudio.google.com/apikey
YOUTUBE_API_KEY=AIza...      # Recomendado
```

### 3. Execute localmente

```bash
python main.py --run          # Executa o agente
python main.py --latest       # Vê os últimos resultados
python main.py --api          # Sobe a API REST
```

## Carrossel diário (Instagram/TikTok)

Gera o pacote de conteúdo de um carrossel por dia para o perfil "Mecanismo Americano": gancho, 6-8 slides (headline + texto + direção visual), legenda para Instagram, legenda para TikTok, hashtags, CTA e **fontes reais citadas** (Census Bureau, BLS, Pew Research, IBGE, Numbeo etc.) para dar credibilidade aos dados usados.

```bash
python main.py --carousel
```

O resultado fica em `outputs/carousel/latest.md` (com legendas, fontes e cada slide já embutido como imagem final) e `outputs/carousel/latest.json`.

**Slides prontos para postar**: para cada slide, a IA gera um `image_query` (termo de busca em inglês) e o agente busca a foto correspondente na [Pexels](https://www.pexels.com/api/) — banco de fotos livre de direitos autorais, uso comercial liberado. Em cima dessa foto, o agente **compõe automaticamente** a headline do slide (com contraste/gradiente para legibilidade), numeração (`1/7`, `2/7`...), a marca "Mecanismo Americano" e o crédito do fotógrafo — gerando um `.jpg` 1080×1350 (formato 4:5 do Instagram) já pronto pra upload, sem precisar abrir Canva. As imagens finais ficam em `outputs/carousel/images/<tema>/slide_N.jpg`. Sem `PEXELS_API_KEY` configurada, o carrossel ainda é gerado normalmente, só sem as fotos/slides finais (fica só o roteiro de texto).

**Não repete tema**: cada execução lê `outputs/carousel/history.json` (commitado no repositório, então sobrevive entre execuções do GitHub Actions) com os últimos tópicos já gerados e pede à IA um ângulo diferente — priorizando as ideias de nicho mais recentes salvas pelo Trends Agent e caindo em temas evergreen só se necessário.

> **Importante:** a foto de fundo vem de um banco de imagens genérico (Pexels), não é gerada sob medida pra cada dado — sempre confira se a imagem escolhida realmente combina com o slide antes de postar, e confira as fontes citadas dos dados.

Roda automaticamente 1x por dia via o workflow `carousel-agent.yml` (10h BRT), logo após o Trends Agent. As fotos baixadas não são commitadas no repositório (ficam fora do git via `.gitignore` para não inchar o histórico) — baixe-as pelo artifact `carousel-<run_id>` na aba **Actions** de cada execução.

## GitHub Actions (execução automática)

Configure os secrets no repositório:

```
Settings → Secrets and variables → Actions → New repository secret
```

| Secret | Descrição |
|--------|-----------|
| `GEMINI_API_KEY` | Chave gratuita do Gemini/Google AI Studio (obrigatório) |
| `YOUTUBE_API_KEY` | Chave do YouTube Data API v3 |
| `PEXELS_API_KEY` | Chave grátis da Pexels, para baixar as fotos do carrossel diário |

O workflow roda automaticamente a cada 4 horas e também pode ser disparado manualmente em **Actions → AI Trends Research Agent → Run workflow**.

Os resultados ficam disponíveis como artifacts e são comitados no branch automaticamente.

## Deploy no Render

1. Fork este repositório
2. Crie um novo Web Service no [Render](https://render.com)
3. Conecte ao repositório — o `render.yaml` configura tudo automaticamente
4. Adicione as variáveis de ambiente no painel do Render

### Endpoints da API

| Método | Rota | Descrição |
|--------|------|-----------|
| `GET` | `/` | Status do serviço |
| `GET` | `/health` | Health check |
| `POST` | `/run` | Dispara o agente |
| `GET` | `/results/latest` | Retorna o último JSON |
| `GET` | `/results/list` | Lista todos os resultados |

## Estrutura do projeto

```
├── .github/workflows/     # GitHub Actions
├── src/
│   ├── agents/            # Orquestrador principal
│   ├── collectors/        # YouTube, Google Trends, RSS
│   ├── analyzers/         # Análise com Gemini
│   ├── storage/           # SQLite
│   ├── exporters/         # JSON e Markdown
│   └── models/            # Pydantic models
├── outputs/
│   ├── json/              # Resultados em JSON
│   └── markdown/          # Relatórios em Markdown
├── main.py                # Entrypoint CLI
├── api.py                 # FastAPI server
├── config.py              # Configurações centralizadas
├── render.yaml            # Deploy Render
└── requirements.txt
```

## Exemplo de saída

```json
{
  "main_topic": "IA substituindo empregos",
  "subtopic": "Automação no mercado brasileiro",
  "score": 92,
  "why_trending": "Demissões em massa em grandes empresas de tecnologia...",
  "hook": "Você vai ser demitido pela IA? Veja os números reais",
  "titles": [
    "A IA vai te demitir em 2025? A verdade que ninguém conta",
    "5 profissões que vão ACABAR com a IA (e o que fazer agora)",
    "Trabalhei com IA por 30 dias e isso aconteceu com meu emprego"
  ],
  "thumbnails": [
    "Rosto chocado + ícone robô + texto: SEU EMPREGO EM RISCO",
    "Gráfico de queda + relógio + texto: COUNTDOWN 2025",
    "Pessoa no computador + IA digital + texto: EU TESTEI"
  ],
  "video_format": "long",
  "urgency": "high",
  "ease": 7
}
```

## Fontes de dados

| Fonte | Região | Tipo |
|-------|--------|------|
| YouTube Data API v3 | BR + US | Vídeos em alta |
| Google Trends | BR + US | Buscas em alta |
| G1 Tecnologia / Economia | BR | RSS |
| CNN Brasil | BR | RSS |
| Exame | BR | RSS |
| Reuters | US | RSS |
| CNN International | US | RSS |
| TechCrunch | US | RSS |
| The Verge | US | RSS |
| Hacker News | US | RSS |

## Score de tendências

O score (0–100) considera:
- **Recência**: quão recente é o conteúdo
- **Views**: volume de visualizações absolutas
- **Velocidade**: views por hora (crescimento)
- **Relevância**: alinhamento com o nicho Brasil × EUA

## Licença

MIT

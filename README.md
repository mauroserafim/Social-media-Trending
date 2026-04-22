# AI Trends Research Agent

Agente automático que varre YouTube, Google Trends e RSS de notícias, identifica temas virais no nicho Brasil × EUA, analisa com IA e gera ideias de vídeos prontas.

## Funcionalidades

- Coleta tendências do YouTube (API oficial), Google Trends e RSS (CNN, Reuters, G1, TechCrunch, etc.)
- Análise com OpenAI (GPT-4o-mini por padrão)
- Gera até 10 ideias por execução com: score, gancho, 3 títulos, 3 thumbnails, formato e urgência
- Exporta em JSON e Markdown
- Armazena histórico em SQLite
- Roda automaticamente via GitHub Actions a cada 4 horas
- API REST opcional (deploy no Render/Railway)

## Configuração rápida

### 1. Clone e configure o ambiente

```bash
git clone https://github.com/seu-usuario/social-media-trending
cd social-media-trending
cp .env.example .env
# Edite .env com suas chaves
pip install -r requirements.txt
```

### 2. Configure as variáveis

Edite `.env`:

```env
OPENAI_API_KEY=sk-...        # Obrigatório
YOUTUBE_API_KEY=AIza...      # Recomendado
```

### 3. Execute localmente

```bash
python main.py --run          # Executa o agente
python main.py --latest       # Vê os últimos resultados
python main.py --api          # Sobe a API REST
```

## GitHub Actions (execução automática)

Configure os secrets no repositório:

```
Settings → Secrets and variables → Actions → New repository secret
```

| Secret | Descrição |
|--------|-----------|
| `OPENAI_API_KEY` | Chave da OpenAI (obrigatório) |
| `YOUTUBE_API_KEY` | Chave do YouTube Data API v3 |

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
│   ├── analyzers/         # Análise com OpenAI
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

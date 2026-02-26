# ForeverFurEver Agent

AI-powered shopping assistant for [foreverfurever.org](https://foreverfurever.org), a Shopify-based pet memorial products store.

**Live:** https://foreverfurever-agent.onrender.com

## What It Does

- Conversational product discovery with emotional awareness (pet loss context)
- Real-time Shopify product search via Storefront GraphQL API
- Knowledge base search (FAQ, brand story, product details, care guides)
- Bilingual support (English / Chinese, auto-detected)
- SSE streaming with product cards, action buttons, and markdown rendering

## Tech Stack

- **Backend:** FastAPI + Uvicorn
- **Agent:** LangGraph (StateGraph) with autonomous tool calling
- **LLM:** Google Gemini 2.0 Flash
- **Knowledge:** TF-IDF search over Notion-synced markdown files
- **Products:** Shopify Storefront GraphQL API (read-only)
- **Frontend:** Vanilla HTML/JS chat widget (standalone + Shopify embed)
- **Deploy:** Render

## Quick Start

```bash
# Clone and setup
git clone <your-repo>
cd ForeverFurEver-Agent
cp .env.example .env   # Fill in API keys

# Install and run
pip install -r requirements.txt
python start.py
```

Open http://127.0.0.1:8000

### Environment Variables

| Variable | Required | Purpose |
|----------|----------|---------|
| `GOOGLE_API_KEY` | Yes | Gemini 2.0 Flash |
| `SHOPIFY_STORE_DOMAIN` | Yes | Storefront API endpoint |
| `SHOPIFY_STOREFRONT_TOKEN` | Yes | Storefront API token |
| `NOTION_TOKEN` | For sync | Notion integration token |
| `NOTION_DATABASE_ID` | For sync | Notion knowledge database ID |
| `ADMIN_TOKEN` | For sync | Admin dashboard auth |

## Tests

```bash
pytest tests/ -v
```

## Deploy to Render

1. Push to GitHub
2. Render Dashboard → **New** → **Blueprint** → connect repo (detects `render.yaml`)
3. Set environment variables in Render dashboard
4. Deploy — `start.py` preloads knowledge then starts Uvicorn

## Docs

- [Project Overview](docs/PROJECT_OVERVIEW.md)

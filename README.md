# ForeverFurEver AI Shopping Agent
Try it: https://foreverfurever-agent.onrender.com/

An AI-powered conversational shopping assistant for a Shopify-based pet memorial store.

## Features

- LLM-driven product recommendation (Gemini 2.0 Flash)
- Real-time Shopify Storefront API integration
- ChromaDB knowledge base (brand info, policies, FAQ)
- LangGraph agent with autonomous tool calling
- Product cards, dynamic actions, bilingual (EN/ZH)

## Tech Stack

- FastAPI + Uvicorn
- LangGraph + LangChain
- Gemini 2.0 Flash (LLM) + Gemini Embedding (vectorization)
- ChromaDB (knowledge retrieval)
- Shopify Storefront GraphQL API
- SQLite (conversation persistence)
- Vanilla JS frontend (Shopify widget-ready)

## Quick Start

### 1. Clone

```bash
git clone <your-repo>
cd ForeverFurEver-Agent
```

### 2. Setup environment

```bash
cp .env.example .env
```

Fill in your `.env`:

```
GOOGLE_API_KEY=your_gemini_api_key
SHOPIFY_STORE_DOMAIN=your-store.myshopify.com
SHOPIFY_STOREFRONT_TOKEN=your_storefront_token
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Index knowledge base

```bash
python -m ff_agent.index_knowledge
```

### 5. Run

```bash
python -m ff_agent.api_server
```

Open http://127.0.0.1:8000

## Deploy to Render

1. Push to GitHub
2. Go to [Render Dashboard](https://dashboard.render.com/) → **New** → **Blueprint**
3. Connect your repo — Render will detect `render.yaml`
4. Set environment variables:
   - `GOOGLE_API_KEY` — Gemini API key from [Google AI Studio](https://aistudio.google.com/)
   - `SHOPIFY_STORE_DOMAIN` — e.g. `your-store.myshopify.com`
   - `SHOPIFY_STOREFRONT_TOKEN` — Shopify Storefront Access Token
5. Deploy. The startup script automatically indexes the knowledge base before starting the server.

Optional env vars:
- `CORS_EXTRA_ORIGINS` — comma-separated extra allowed origins (e.g. your Render URL)

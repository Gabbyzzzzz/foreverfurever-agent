# ForeverFurEver Agent — Project Overview

## 1. What This Is

ForeverFurEver Agent is an **AI-powered shopping assistant** for [foreverfurever.org](https://foreverfurever.org), a pet memorial products store on Shopify. It is embedded as a conversational widget on the storefront, helping visitors find the right memorial product while being sensitive to the emotional context of pet loss.

Core capabilities:

- **Autonomous reasoning** — Decides when to query the Shopify product catalog, when to search the knowledge base, when to ask a clarifying question, and when to escalate to human support
- **Tool orchestration** — Coordinates multiple tools (product search, knowledge lookup, product details) through LangGraph's state machine, with single or multi-round tool calls
- **Emotional awareness** — System prompt designed for warmth, empathy, and restraint in a grief-sensitive context
- **Bilingual** — Automatically detects and switches between English and Chinese

**The core job:** Turn a grieving pet owner's vague intent ("I want something to remember my cat") into a confident purchase — through intelligent product discovery, policy lookup, and emotionally appropriate guidance — without pressure, without hallucinated information, and without requiring a human support agent for 90%+ of inquiries.

| | |
|---|---|
| **Live URL** | https://foreverfurever-agent.onrender.com |
| **Store** | https://foreverfurever.org |
| **LLM** | Google Gemini 2.0 Flash |
| **Framework** | LangGraph (StateGraph) on FastAPI |
| **Deploy** | Render (free tier) |
| **Languages** | English (default), Chinese (auto-detected) |

---

## 2. Why It Exists

Pet memorial is an emotionally sensitive purchase. Customers don't browse casually — they arrive in grief, often unsure what they need. A traditional product page with specs and "Add to Cart" doesn't serve them well, and queries like "I just lost my cat and I don't know what I want" need a smarter approach.

ForeverFurEver Agent fills this gap:
- **Intelligent product discovery** — Decides which tools to call based on intent: product search, knowledge lookup, or both
- **Emotional safety** — Warm tone, never pushy, never inappropriately cheerful. System prompt designed for grief-sensitive interaction
- **Instant policy answers** — Shipping times, return policies, customization options without waiting for email support
- **Bilingual** — Automatically detects and switches to Chinese, reflecting the store's customer base
- **Escalation judgment** — Knows when to hand off to human support (refund requests, damaged items) vs. when it can handle the inquiry itself

---

## 3. Current Product Catalog

| Product | Price | What It Is |
|---------|-------|------------|
| **TravelStar Companion** | $117.00 | Portable pet urn — bio-composite sphere (10cm, 210g), hand-engraved, dual-layer sealed, air travel safe |
| **Eternal Glow** | $40.00 | Personalized nightlight — 3D relief sculpted from pet photo, USB powered, illuminated memorial |

Both products support text-only personalization (engraving). All customization is included in price. Shopify is the source of truth for product data — the agent queries it live via GraphQL.

---

## 4. Architecture

### 4.1 System Overview

```
┌─────────────────────────────────────────────────────────┐
│                    Shopify Storefront                     │
│                  foreverfurever.org                       │
│  ┌──────────────────────────────────────────────────┐   │
│  │            embed.js (chat widget)                 │   │
│  │   Floating button → iframe → SSE streaming        │   │
│  └──────────────────┬───────────────────────────────┘   │
└─────────────────────┼───────────────────────────────────┘
                      │ POST /chat/stream (SSE)
                      ▼
┌─────────────────────────────────────────────────────────┐
│                 Render (Python server)                    │
│                                                          │
│  ┌──────────┐   ┌──────────────────────────────────┐    │
│  │ FastAPI   │──▶│         LangGraph Agent           │    │
│  │ /chat     │   │                                    │    │
│  │ /chat/    │   │  preprocess → agent ⇄ tools →     │    │
│  │  stream   │   │                      postprocess   │    │
│  └──────────┘   └────────┬──────────┬────────────────┘    │
│                          │          │                      │
│              ┌───────────▼┐  ┌──────▼──────────┐          │
│              │ Gemini 2.0  │  │ Knowledge Base  │          │
│              │ Flash (LLM) │  │ (TF-IDF, local) │          │
│              └─────────────┘  └─────────────────┘          │
│                          │                                  │
│              ┌───────────▼──────────────┐                  │
│              │ Shopify Storefront API    │                  │
│              │ (GraphQL, read-only)      │                  │
│              └──────────────────────────┘                  │
└─────────────────────────────────────────────────────────┘
```

### 4.2 Request Flow

A single user message triggers this pipeline:

1. **Preprocess** — Detect language (English/Chinese) from CJK character ratio
2. **Agent** — Gemini receives: system prompt + KB context (for policy queries) + conversation history + user message. Decides whether to call tools or respond directly.
3. **Tools** (0 or more rounds) — Gemini autonomously calls `search_products`, `search_knowledge`, `get_product_details`, or `get_collection` as needed. It may call multiple tools or loop back for more.
4. **Postprocess** — Extract product data from tool results for UI cards. Detect escalation triggers (support email mention) and generate action buttons.
5. **Response** — Stream tokens via SSE, then send product cards and action buttons as separate SSE events.

### 4.3 Streaming

The primary endpoint is `POST /chat/stream` (SSE). Events:

| Event Type | Payload | When |
|-----------|---------|------|
| `start` | `{thread_id}` | Connection established |
| `token` | `{text}` | Each LLM token as it's generated |
| `products` | `{products: [...]}` | Product cards from tool results |
| `actions` | `{actions: [...]}` | UI buttons (e.g., "Email Support") |
| `done` | `{}` | Stream complete |
| `error` | `{text}` | On failure |

Fallback: `POST /chat` returns a complete JSON response (used when SSE is unavailable, e.g., older browsers).

---

## 5. Knowledge System

### 5.1 How It Works

Knowledge is stored as **markdown files** in the `knowledge/` directory, sourced from Notion. At startup, all files are loaded into memory, split into ~79 chunks by markdown headers, and indexed using pure Python TF-IDF.

When a user asks about policies, shipping, returns, customization, or brand information, the agent node detects policy-related keywords and injects relevant KB chunks into the system prompt before calling Gemini.

### 5.2 Knowledge Files

| File | Category | Content |
|------|----------|---------|
| `FAQ.md` | faq | Customization, shipping (10-13 days), returns (final sale for custom), care |
| `BrandStory–AboutForeverFurEver.md` | brand | Origin story (founder's cat Molly), philosophy, mission |
| `ProductKnowledge–TravelStar Companion.md` | product | Specs (10cm/210g), features, materials, personalization details |
| `ProductKnowledge–Eternal Glow.md` | product | Concept, 4-step creation process, photo requirements |
| `HowtoUse&Care.md` | care | Material handling, maintenance instructions |

### 5.3 Why TF-IDF Instead of Vector DB

The knowledge base is 5 files / ~79 chunks. Vector databases (ChromaDB was tried) introduced:
- gRPC transport errors on Render ("503 Illegal metadata")
- Cold start latency for embedding generation
- An external dependency for what is fundamentally a keyword search over a tiny corpus

TF-IDF with Python's `collections.Counter` is fast, dependency-free, and perfectly adequate at this scale. If the catalog grows to 50+ products or the KB to 500+ chunks, migration to a vector DB would make sense.

### 5.4 Notion Sync

Knowledge is authored in Notion and synced to markdown via the admin dashboard:

```
Notion Database (pages with Status="Published")
       │
       ▼  POST /admin/sync-knowledge (token-protected)
notion_sync.py
       │  Notion REST API → blocks → markdown conversion
       ▼
knowledge/*.md files (overwritten)
       │
       ▼
knowledge.py reload (TF-IDF re-indexed in memory)
```

The sync handles: paragraphs, headings (H1-H3), bulleted/numbered lists, dividers, quotes, and rich text formatting (bold, italic, code). It updates the "Last Synced" timestamp in Notion after each successful page sync.

---

## 6. Shopify Integration

### 6.1 Storefront API (GraphQL)

The agent queries Shopify's Storefront API (read-only, no authentication required beyond the public token) for:

- **Product search** — Full-text search across title, description, tags, vendor
- **Product details** — Variants, pricing, availability, images
- **Collection browsing** — Products by collection handle

### 6.2 Search Strategy

```python
search_products("urn", max_results=6)
```

1. Execute full-text search with user's keywords
2. If results < max_results, supplement with latest products (ensures the full catalog is visible for small stores)
3. Deduplicate by product handle
4. Return standardized product dicts with: title, handle, description, product_type, tags, price, url, image_url, checkout_url

### 6.3 Dynamic Product Understanding

The system prompt does **not** contain a hardcoded product catalog. Instead, Gemini reads product metadata (title, description, product_type, tags) from Shopify's tool results to understand what each product is. This means:

- Adding new products to Shopify → agent discovers them automatically
- Changing product titles for SEO → agent adapts without code changes
- Product availability changes → reflected in real-time

The tradeoff: if Shopify products have empty descriptions/tags (currently the case), Gemini relies on title alone to understand the product.

### 6.4 Image Optimization

Product images are requested with Shopify's image transform API:
```graphql
url(transform: {maxWidth: 400, maxHeight: 400, preferredContentType: JPG})
```
This converts raw uploads (potentially 1MB+ HEIC) to ~15KB optimized JPEGs for fast loading in the chat widget.

---

## 7. Chat Widget (Frontend)

### 7.1 Standalone Page

`static/chat.html` — Full chat interface served at the root URL. Features:

- **SSE streaming** with token-by-token display, markdown rendering, fallback to `/chat`
- **Product cards** in a frosted-glass overlay (semi-transparent purple, `backdrop-filter: blur`) with collapse/expand toggle
- **Starter suggestion chips** — 4 quick-start buttons (Browse Products, Find an Urn, Shipping & Returns, Help Me Choose) shown on greeting
- **Conversation persistence** — Chat history saved to localStorage per thread, restored on page reload
- **Clear/reset button** — Generates new thread_id, clears history, shows fresh greeting
- **Email Support button** — Auto-generated when AI mentions `support@foreverfurever.org`
- **Conversion tracking** — Product impressions, clicks, buy button clicks sent to `/track`

### 7.2 Shopify Embed

`static/embed.js` — Drop-in script for the Shopify storefront:

```html
<script src="https://foreverfurever-agent.onrender.com/static/embed.js"></script>
```

Creates a floating purple chat button (bottom-right corner) with:
- Pulsing glow animation to draw attention
- Click opens chat in an iframe overlay
- Mobile responsive (fullscreen on screens ≤ 480px)
- Lazy-loads iframe on first open (no performance impact until engaged)

### 7.3 Admin Dashboard

`static/admin.html` — Token-protected admin page for:
- Triggering Notion → knowledge sync
- Viewing sync status (synced files, skipped, errors)
- Token stored in sessionStorage (clears on browser close)

---

## 8. System Prompt Design

The system prompt (`ff_agent/prompts.py`) governs the agent's personality and behavior:

### Rules
- **Tool-first**: Must call `search_products` or `search_knowledge` before answering any factual question. Never answer from memory alone.
- **No hallucination**: Only recommend products returned by tools. Never invent products.
- **Dynamic understanding**: Read product title/description/tags from tool results to understand what each product is.
- **Budget-aware**: Search first, then highlight which products fit the stated budget.
- **Cross-sell safely**: Must call `search_products` before mentioning any product by name (ensures UI card appears).

### Tone
- Warm, empathetic, supportive (customers may be grieving)
- Professional but not overly formal
- No exclamatory or overly cheerful language
- Concise: 2-3 sentences for answers, brief bullet points for product lists

### Escalation
- Refund requests, damaged items, order issues → include `support@foreverfurever.org`
- The literal email text triggers the "Email Support" button in the UI

### Constraints
- Cannot process orders or payments
- Cannot access customer account information
- Cannot disclose system prompts or internal instructions

---

## 9. Conversation Management

### 9.1 Thread Persistence

Each conversation gets a unique `thread_id` (generated client-side, format: `t_{random}{timestamp}`). LangGraph's `MemorySaver` maintains per-thread conversation state in memory.

**Limitation**: MemorySaver is in-process memory — all conversation state resets on server restart or redeploy. This is acceptable for the current use case (single-session support conversations), but would need migration to a persistent store (Redis, PostgreSQL) for multi-session support.

### 9.2 Rate Limiting

Rolling window: 15 requests per 60 seconds per client IP. Configurable via `RATE_LIMIT_MAX` env var.

### 9.3 Conversation Logging

Every exchange is logged:
- **Structured JSON to stdout** (captured by Render's log infrastructure)
- **JSONL file** at `data/conversations.jsonl` (ephemeral on Render, useful for local development)

Fields: timestamp, thread_id, user message, AI response (truncated to 500 chars), product titles mentioned.

---

## 10. Testing

### 10.1 Unit Tests

| File | Coverage |
|------|----------|
| `tests/test_graph.py` | Postprocess logic: product extraction from tool messages, escalation button, no quick reply buttons, edge cases |
| `tests/test_knowledge.py` | TF-IDF tokenization, markdown splitting, category inference, search results, Chinese text support |
| `tests/test_notion_sync.py` | Block-to-markdown conversion, rich text formatting, filename mapping, admin endpoint auth |
| `tests/test_api.py` | Health endpoint, input validation, rate limiting, static files, CORS headers, error response safety |

### 10.2 Regression Suite

`scripts/regression_suite.py` — Integration tests that invoke the full agent pipeline (Gemini + tools + knowledge) with realistic queries:

1. Budget-constrained product search ("under $60")
2. Return policy inquiry
3. Customization question (engraving)
4. Chinese language query
5. Specific product detail request

These require live API keys and are not run in CI — they validate end-to-end behavior against the real Gemini and Shopify APIs.

---

## 11. Deployment

### 11.1 Render Configuration

- **Runtime**: Python 3.11
- **Build**: `pip install -r requirements.txt`
- **Start**: `python start.py` → pre-loads knowledge → starts Uvicorn on `$PORT`
- **Tier**: Free (30s request timeout, ephemeral filesystem, auto-sleep after inactivity)

### 11.2 Environment Variables

| Variable | Required | Purpose |
|----------|----------|---------|
| `GOOGLE_API_KEY` | Yes | Gemini 2.0 Flash API access |
| `SHOPIFY_STORE_DOMAIN` | Yes | Storefront API endpoint (e.g., `66pqxy-de.myshopify.com`) |
| `SHOPIFY_STOREFRONT_TOKEN` | Yes | Public Storefront API token |
| `NOTION_TOKEN` | For sync | Notion integration token |
| `NOTION_DATABASE_ID` | For sync | Notion knowledge database ID |
| `ADMIN_TOKEN` | For sync | Admin dashboard authentication |
| `CORS_EXTRA_ORIGINS` | No | Comma-separated additional allowed origins |
| `RATE_LIMIT_MAX` | No | Requests per minute per IP (default: 15) |
| `SYNC_INTERVAL_HOURS` | No | Auto-sync interval (disabled by default) |

### 11.3 CORS

Whitelisted origins:
- `https://foreverfurever.org` / `https://www.foreverfurever.org`
- `https://foreverfurever.myshopify.com`
- `https://admin.shopify.com`
- `http://localhost:8000` / `http://127.0.0.1:8000`
- Additional via `CORS_EXTRA_ORIGINS`

---

## 12. File Structure

```
ForeverFurEver-Agent/
├── ff_agent/
│   ├── __init__.py
│   ├── api_server.py          # FastAPI server, SSE streaming, rate limiting, logging
│   ├── graph.py               # LangGraph state graph (preprocess → agent ⇄ tools → postprocess)
│   ├── prompts.py             # System prompt definition
│   ├── tools.py               # LangChain tool wrappers (search_products, search_knowledge, etc.)
│   ├── shopify_storefront.py  # Shopify Storefront GraphQL client
│   ├── knowledge.py           # In-memory TF-IDF knowledge search
│   └── notion_sync.py         # Notion → markdown sync (REST API)
├── knowledge/                 # Markdown knowledge files (synced from Notion)
│   ├── FAQ.md
│   ├── BrandStory–AboutForeverFurEver.md
│   ├── ProductKnowledge–TravelStar Companion.md
│   ├── ProductKnowledge–Eternal Glow.md
│   └── HowtoUse&Care.md
├── static/
│   ├── chat.html              # Full chat UI (standalone page)
│   ├── embed.js               # Shopify embed widget (floating button + iframe)
│   └── admin.html             # Admin dashboard for Notion sync
├── tests/
│   ├── test_graph.py          # Postprocess logic tests
│   ├── test_knowledge.py      # TF-IDF search tests
│   ├── test_notion_sync.py    # Notion sync + admin endpoint tests
│   └── test_api.py            # API endpoint tests
├── scripts/
│   ├── regression_suite.py    # End-to-end integration tests
│   ├── push_to_notion.py      # Utility: push local knowledge to Notion
│   └── test_shopify_storefront.py  # Shopify API diagnostic script
├── start.py                   # Entry point (knowledge preload + Uvicorn)
├── render.yaml                # Render deployment blueprint
├── requirements.txt           # Python dependencies
└── docs/
    └── PROJECT_OVERVIEW.md    # This document
```

---

## 13. Design Decisions & Rationale

### Why Gemini 2.0 Flash (not GPT-4 / Claude)
- Generous free tier for a bootstrapping e-commerce store
- Fast response times (~2-4s for tool-calling flows)
- Native function calling support via LangChain integration
- Adequate quality for customer service with well-crafted system prompts

### Why TF-IDF (not Vector DB)
- 5 files, ~79 chunks — vector search is overkill
- ChromaDB caused persistent gRPC 503 errors on Render's free tier
- Pure Python implementation: zero external dependencies, instant startup
- Perfectly adequate for keyword-driven policy lookups

### Why MemorySaver (not SQLite/Redis)
- Single-session conversations (support chat, not long-term relationships)
- Render free tier has ephemeral filesystem (SQLite would be lost on redeploy anyway)
- No user accounts or conversation history requirements
- Eliminates database dependency for a simpler deployment

### Why SSE Streaming (not WebSocket)
- Simpler server implementation (standard HTTP, no upgrade negotiation)
- Works through more proxies and CDNs
- Render's free tier handles SSE well
- Automatic fallback to non-streaming endpoint for compatibility

### Why Notion for Knowledge (not CMS/Database)
- Store owner already uses Notion for business operations
- WYSIWYG editing with rich text, no technical knowledge required
- One-click sync via admin dashboard
- Revision history and collaboration built in

---

## 14. Known Limitations

1. **Conversation state is ephemeral** — Resets on every server restart/redeploy. Customers lose context if the server cycles during their conversation.
2. **Render free tier cold starts** — First request after inactivity may take 30-60s as the server spins up.
3. **Product descriptions are empty in Shopify** — The AI relies primarily on product titles to understand what each product is. Adding descriptions and tags in Shopify admin would significantly improve recommendation accuracy.
4. **No order tracking** — Cannot look up order status, shipment tracking, or customer account information.
5. **No payment processing** — Can guide to checkout URL but cannot complete transactions.
6. **Rate limiting is per-IP** — Shared IPs (corporate networks, VPNs) may hit limits unfairly.

---

## 15. Future Directions

### Near-term
- **Shopify product metadata** — Add descriptions, tags, and product types in Shopify admin so the AI can better understand and categorize products
- **Persistent conversation storage** — Migrate to Redis or PostgreSQL when conversation history becomes a product requirement
- **Analytics dashboard** — Visualize conversation logs, conversion rates, popular queries, drop-off points

### Medium-term
- **Vector search upgrade** — When the catalog grows beyond ~20 products, migrate knowledge search from TF-IDF to a hosted vector DB (Pinecone, Weaviate, or pgvector)
- **Order status integration** — Connect to Shopify Admin API for order tracking
- **Multi-product comparison** — Side-by-side feature comparison when customers are deciding between products
- **Proactive engagement** — Trigger chat widget based on browsing behavior (e.g., 30s on product page without action)

### Long-term
- **B2B operations agent** — Internal agent for inventory, supplier management, order processing
- **Voice support** — Audio input/output for accessibility
- **A/B testing framework** — Test different system prompts, greeting messages, and recommendation strategies against conversion metrics

---

## 16. Dependencies

```
fastapi          # Web framework
uvicorn          # ASGI server
python-dotenv    # Environment variable loading
langgraph        # Agent orchestration (StateGraph)
langchain-google-genai  # Gemini LLM integration
google-generativeai     # Gemini API client
requests         # HTTP client (Shopify GraphQL, Notion REST)
```

---

*Last updated: 2026-02-26*

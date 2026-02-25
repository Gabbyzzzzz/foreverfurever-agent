# ForeverFurEver — AI-Powered Ecommerce Operations & Customer Experience System

## 1. Project Summary

ForeverFurEver is an **AI-native ecommerce brand** specializing in pet memorial products (urns, keepsakes, engraved jewelry). The project is an AI-powered customer-facing chatbot that provides product guidance, FAQ answers, and guided shopping for a DTC (Direct-to-Consumer) Shopify store.

| System | Role | Tech Stack | User |
|--------|------|------------|------|
| **ForeverFurEver Agent** (B2C) | Customer-facing chatbot — product guidance, FAQ, guided shopping | FastAPI + LangGraph + GPT + Shopify Storefront API | Website visitors |

**Brand Identity:**
- Positioning: Pet memorial, emotional support, respectful and calm
- Tone: Warm, gentle, trustworthy, not pushy
- Website: https://foreverfurever.org
- Shopify Store: 66pqxy-de.myshopify.com

---

## 2. System Architecture

```
                    ┌─────────────────────────────────────────────┐
                    │              ForeverFurEver Brand            │
                    │           foreverfurever.org (Shopify)       │
                    └────────────────────┬────────────────────────┘
                                         │
                            ┌────────────▼──────────┐
                            │  ForeverFurEver Agent  │
                            │  (Customer-facing)     │
                            ├────────────────────────┤
                            │ FastAPI                │
                            │ LangGraph              │
                            │ GPT                    │
                            │ Shopify Storefront API │
                            │ Chat Widget            │
                            └────────────────────────┘
```

---

## 3. Customer Agent (ForeverFurEver Agent)

### 3.1 Purpose
An embedded chat widget on the Shopify storefront that guides visitors through product discovery, answers FAQs, and provides emotionally appropriate shopping assistance.

### 3.2 Core Capabilities
- **Product Explanation** — Clarifies that products support TEXT-ONLY personalization (not pet image customization)
- **FAQ & Policy Answers** — Shipping, returns, customization rules
- **Guided Shopping** — Budget-aware recommendations from real Shopify product data
- **Multi-turn Conversation** — Clarify needs → Recommend → Quick-action buttons
- **Quick Actions** — Button-based interactions (Urn / Keepsake / Browse all) to reduce user friction

### 3.3 Technical Architecture

```
User Input
    │
    ▼
┌──────────────┐    ┌───────────────┐    ┌──────────────────┐
│ Chat Widget  │───▶│ FastAPI /chat │───▶│ LangGraph Agent  │
│ (HTML+JS)    │    │   (CORS OK)   │    │                  │
└──────────────┘    └───────────────┘    │  router          │
                                         │    ▼             │
                                         │  intent classify │
                                         │  (policy/product │
                                         │   /custom/other) │
                                         │    ▼             │
                                         │  needs_clarify?  │
                                         │  ┌──▶ clarify    │
                                         │  │    node       │
                                         │  └──▶ answer     │
                                         │       node       │
                                         └────────┬─────────┘
                                                  │
                                    ┌─────────────▼──────────────┐
                                    │ Shopify Storefront API     │
                                    │ (GraphQL product search)   │
                                    └────────────────────────────┘
```

### 3.4 Key Design Decisions
- **Slot-based Profile Engineering** — Structured user preferences (budget, occasion, style, deadline, engraving) instead of raw chat history. Lower cost, more stable behavior.
- **Non-RAG Knowledge Injection** — Brand knowledge injected via system prompt (no vector DB needed for MVP)
- **Budget-aware Filtering** — Products filtered by user budget before recommendation; max 1 over-budget suggestion
- **Choice-to-Profile Wiring** — UI button clicks map directly to profile slots (`#choice:occasion=gift`), bypassing LLM extraction for deterministic behavior
- **API Response Contract** — Unified response schema: `{ type, intent, content, profile, actions, products_debug, tool_error, version }`

### 3.5 Evolution Stages

| Stage | Milestone |
|-------|-----------|
| 1.0 | Minimum API — FastAPI + GPT endpoint |
| 2.0 | Brand knowledge injection via system prompt |
| 3.0 | LangGraph state machine (router → answer) |
| 3.5 | Clarification node for ambiguous queries |
| 3.6 | Session memory via thread_id |
| 3.7 | Slot-based profile engineering |
| 3.8 | Shopify Storefront API integration (real products) |
| 3.8.2 | Budget-aware recommendation filtering |
| 3.8.3 | Fuzzy-need handling + lightweight follow-up |
| 3.9 | Quick action buttons (non-LLM generated) |
| 4.0 | API response contract finalization |
| 4.1 | Local chat widget (HTML+JS) |
| 4.2 | Guided shopping flow |
| 4.3 | Choice-to-profile wiring (deterministic) |
| 4.4 | Shopify embed + CORS + Render deployment |

---

## 4. Technology Stack Summary

| Component | Technology | Purpose |
|-----------|-----------|---------|
| **Backend** | FastAPI + Python | Chat API server |
| **Orchestration** | LangGraph (StateGraph) | Multi-step conversation flow |
| **LLM** | OpenAI GPT | Customer-facing responses |
| **Data Source** | Shopify Storefront API (GraphQL) | Real product data for recommendations |
| **Frontend** | HTML + JS Chat Widget | Embedded on Shopify store |
| **Hosting** | Render | Cloud deployment |
| **Memory** | LangGraph MemorySaver | Per-thread conversation state |

---

## 5. Data Flow Overview

### Customer Journey
```
Visitor lands on foreverfurever.org
    → Opens chat widget
    → "I want something to remember my dog, under $50"
    → Agent: extracts profile {budget: 50, occasion: memorial}
    → Agent: queries Shopify Storefront API (products under $50)
    → Agent: recommends "Eternal Glow" ($47) with personalization details
    → Visitor clicks Quick Action: "Tell me more"
    → Agent: provides detail + gentle CTA to add to cart
```

---

## 6. Key Design Principles

1. **Tools over Hallucination** — Agent always calls external tools/APIs for real data. Never guess numbers or invent products.
2. **Emotional Safety** — No medical/mental health claims, no pressure-selling, no sensitive data collection.
3. **Deterministic where possible** — Quick actions, profile slots, and response contracts are rule-based (not LLM-generated) to ensure stability.
4. **Memory as engineering** — Slot-based profiles instead of full conversation replay.

---

## 7. Product Catalog Reference

| Product | Price | Type | Personalization |
|---------|-------|------|-----------------|
| Eternal Glow – A Soulful Tribute | ~$47 | Memorial keepsake | Text engraving (name, date, inscription) |
| TravelStar Companion – Portable Pet Keepsake | ~$117 | Portable memorial | Text engraving, lightweight & durable |

- All personalization is **TEXT-ONLY** (not pet image/photo customization)
- Free engraving included
- Focus on emotional companionship, not traditional "urn" positioning

---

## 8. File Structure

```
ForeverFurEver-Agent/
├── api_server.py                   # FastAPI main server
├── graph/                          # LangGraph agent definition
│   ├── router.py                   # Intent classification
│   ├── clarify.py                  # Clarification node
│   ├── answer.py                   # Answer generation + Shopify query
│   └── profile.py                  # Slot-based profile extraction
├── tools/                          # Shopify Storefront API tools
├── docs/
│   ├── 00_project_log.md           # Development evolution log
│   ├── 01_store_knowledge.md       # Brand knowledge (injected to system prompt)
│   └── PROJECT_OVERVIEW.md         # This document
└── frontend/                       # Chat widget (HTML+JS)
```

---

## 9. Future Roadmap

- Product compare & rank node
- Operator-editable knowledge base (no code deploys)
- Lightweight analytics & conversion tracking
- High-concurrency optimization

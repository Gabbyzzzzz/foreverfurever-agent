# ForeverFurEver AI Shopping Agent

An AI-powered conversational shopping assistant for a Shopify-based pet memorial store.

## Features

- Budget-aware product recommendation
- Real-time Shopify Storefront API integration
- LangGraph agent flow (intent routing + clarification + actions)
- Interactive web demo UI

## Tech Stack

- FastAPI
- LangGraph
- OpenAI GPT
- Shopify Storefront API
- Vanilla JS frontend

## Demo

Run locally in 1 minute:

python -m ff_agent.api_server

## Quick Start

### 1. Clone

git clone <your-repo>
cd ForeverFurEver-Agent

### 2. Setup environment

cp .env.example .env

Fill in:

OPENAI_API_KEY=your_key_here
SHOPIFY_STOREFRONT_TOKEN=your_token_here

### 3. Install dependencies

pip install -r requirements.txt

### 4. Run

python -m ff_agent.api_server

### 5. Open in browser

http://127.0.0.1:8000

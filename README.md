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

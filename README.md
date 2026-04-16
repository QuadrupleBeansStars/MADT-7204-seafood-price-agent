# Bangkok Seafood Price Advisor — Agentic AI

> MADT 7204 Vibe Coding Project | Bangkok Oil Price Crisis

## Team

| Student ID | Name | Role |
|------------|------|------|
| 6810424003 | Nititorn Chawanpunya | **IT Lead** |
| 6810414003 | Thanaree Raksaman | Mgmt Member |
| 6810424002 | Kanyathat Rakdee | Mgmt Member |
| 6810424011 | Natta Chaisiripant | Mgmt Member |
| 6810424014 | Phawinee Jinapang | Mgmt Member |

## Problem Statement

Thailand's oil price crisis has driven up fuel and cold-chain logistics costs, making seafood prices volatile across Bangkok markets. Restaurants, wholesalers, and households struggle to find the best deals as prices shift daily across vendors.

This agent solves that by scraping daily seafood prices from multiple Bangkok markets, comparing them across shops and SKUs, and recommending where to buy — saving time and money for anyone purchasing seafood in bulk.

## Agent Design

This project uses a **LangGraph ReAct agent** with a tool-calling feedback loop and **Langfuse** for full observability.

- **Framework**: LangGraph (graph-based agent with cycles)
- **LLM**: Anthropic Claude Sonnet 4.5 (via LangChain)
- **Observability**: Langfuse (self-hosted, auto-tracing every LLM call and tool use)
- **UI**: Streamlit chatbot with password gate + auto-mounted dashboards

### How It Works

```
User asks: "What are today's best seafood deals?"
  → Agent reasons about the question
  → Calls get_best_deals tool
  → Tool queries the price database (Pandas on CSV)
  → Returns top deals >10% below market average
  → Agent formulates a recommendation
  → User sees: best price, shop, % saved vs market
```

### Tools

| Tool | Description |
|------|-------------|
| `query_seafood_prices` | Query prices by item, shop, and date |
| `get_best_deals` | Find items priced >10% below the market average (top 5) |
| `get_price_trend` | Show price history for an item across shops over the last N days |

### Example prompts that exercise tool calls

- **`query_seafood_prices`** → *"How much is white shrimp at Makro today?"*
- **`get_best_deals`** → *"What are today's top seafood bargains?"*
- **`get_price_trend`** → *"Has salmon gone up this week?"*
- **Multi-step** → *"Compare white shrimp across all shops today and tell me if the cheapest one is a genuine deal or just normal pricing."* (chains `query_seafood_prices` → `get_best_deals`)

In the Streamlit chat, expand the **🔧 Tool calls** panel under each assistant reply to see which tools ran and their raw output.

### Data Pipeline

Daily scraped seafood prices are stored in CSV format with columns:
`date`, `shop`, `sku`, `item_name`, `category`, `price_per_kg`, `unit`, `available`

Currently using synthetic sample data (5 shops, 16 SKUs, 7 days). Real scraping targets to be identified by the management team.

## Data Sources

| Source | Type | Usage |
|--------|------|-------|
| Bangkok seafood markets | Scraped (daily) | Price comparison across shops |
| Sample data generator | Synthetic | Development and demo |

## Setup

```bash
# 1. Clone the repo
git clone <repo-url>
cd <project-folder>

# 2. Create conda environment
conda create -n MADT python=3.11 -y
conda activate MADT

# 3. Install dependencies
pip install -r requirements.txt

# 4. Set up environment variables
cp .env.example .env
# Edit .env — set ANTHROPIC_API_KEY (from console.anthropic.com) and
# optional LANGFUSE_* keys. APP_PASSWORD is the fallback login password
# when .streamlit/secrets.toml isn't present (useful for local dev).

# 5. Set the Streamlit login password (and optionally mirror secrets)
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
# Edit .streamlit/secrets.toml — at minimum change app_password.
# ANTHROPIC_API_KEY can live in either .env or secrets.toml; env wins
# if both are set. For local dev .env is fine; for Streamlit Cloud
# deploy the key must go in secrets (see next section).

# 6. Generate sample data
python data/scripts/generate_sample_data.py

# 7a. Run the agent (CLI)
python -m agent.main

# 7b. Or run the Streamlit chatbot UI
streamlit run app/main.py
```

### Deploying to Streamlit Community Cloud

1. Push to GitHub.
2. Create the app at [share.streamlit.io](https://share.streamlit.io/), pointing to `app/main.py`.
3. In the app's **Secrets** section, paste:
   ```toml
   app_password = "your-shared-password"
   ANTHROPIC_API_KEY = "sk-ant-..."
   ```
4. The password gate protects the chat **and** the auto-mounted dashboards — visitors can't reach `/dashboard` or `/shop_profile` without logging in.

## Vibe-Coding Tools Used

| Tool | Used For |
|------|----------|
| Claude Code | Agent architecture scaffolding, code generation, project planning |

## Known Limitations

- Currently uses synthetic sample data (real scraping in Week 2)
- Login is a single shared password (good enough for a class demo; swap to per-user auth before any production use)
- 3 tools implemented (`calculate_order_cost` on an in-flight feature branch)

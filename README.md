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

Thailand's oil price crisis has driven up fuel and cold-chain logistics costs, making seafood prices volatile across Bangkok vendors. Restaurants, wholesalers, and households struggle to find the best deals as prices shift daily across online shops.

This agent solves that by scraping daily seafood prices from 7 real Bangkok seafood e-commerce websites, comparing them across shops and product options, and recommending where to buy — saving time and money for anyone purchasing seafood in bulk.

## Agent Design

This project uses a **LangGraph ReAct agent** with a tool-calling feedback loop, powered by **Anthropic Claude Sonnet 4.5** and observed with **Langfuse**.

- **Framework**: LangGraph (graph-based agent with cycles)
- **LLM**: Anthropic Claude Sonnet 4.5 (via LangChain)
- **Observability**: Langfuse (auto-tracing every LLM call and tool use)
- **UI**: Streamlit with 3 pages — Chat (agent), Price Dashboard, Shop Profiles
- **Language**: Fully bilingual (Thai and English) — the agent responds in the same language the user writes in

### How It Works

```
User asks: "วันนี้อาหารทะเลอะไรราคาดีบ้าง?"
  → Agent reasons about the question (Thai → Thai response)
  → Calls get_best_deals tool
  → Tool queries real scraped price data (Pandas on CSV)
  → Returns top deals >10% below market average with product links
  → Agent formulates a Thai recommendation with order table
  → User sees: best prices, shops, % saved, clickable order links
```

### Tools

| Tool | Description |
|------|-------------|
| `query_seafood_prices(item, shop?)` | Query prices by item name (EN/TH), optionally filtered by shop |
| `get_best_deals(category?)` | Find items priced >10% below market average (top 5 deals) |
| `get_price_trend(item, days?)` | Show price trend across shops over last N days (or price spread if only snapshot data) |
| `calculate_order_cost(items, shop?)` | Calculate total order cost for a shopping list including transport fees *(feature branch)* |

### Example prompts

| Tool exercised | English | Thai |
|---|---|---|
| `query_seafood_prices` | "How much is tiger prawn?" | "กุ้งลายเสือราคาเท่าไหร่?" |
| `get_best_deals` | "What are today's best seafood deals?" | "วันนี้ซีฟู้ดอะไรดีลเด็ดบ้าง?" |
| `get_price_trend` | "Compare salmon prices across all shops" | "เปรียบเทียบราคาแซลมอนทุกร้าน" |
| Multi-step | "I need 2kg tiger prawn and 1kg sea bass — which shop is cheapest?" | "ฉันต้องการกุ้งลายเสือ 2 กก. ร้านไหนถูกที่สุด?" |

In the Streamlit chat, expand the **Tool calls** panel under each assistant reply to see which tools ran and their raw output.

## Data Sources

| Source | Type | Products | Usage |
|--------|------|----------|-------|
| [ไต้ก๋ง ซีฟู้ด (Taikong Seafood)](https://taikongseafood.com) | Scraped (daily) | 30 | WooCommerce, variant pricing |
| [Sawasdee Seafood](https://www.sawasdeeseafood.com) | Scraped (daily) | 18 | WooCommerce, single-SKU |
| [HENG HENG Seafood](https://www.henghengseafood.com) | Registry (static) | 46 | JS-only pricing, falls back to registry |
| [PPNSeafood](https://www.ppnseafoodwishing.com) | Scraped (daily) | 55 | WooCommerce, variant pricing |
| [Supreme Seafoods](https://supremeseafoods.net) | Scraped (daily) | 44 | Page365 JSON API |
| [Sirirat Seafood](https://siriratseafood.com) | Scraped (daily) | 26 | WooCommerce, variant pricing |
| [Sirin Farm](https://www.sirinfarm.com) | Scraped (daily) | 10 | WooCommerce, single-SKU |

**Total**: ~229 products across 5 categories (shrimp, fish, squid, crab, shellfish) with both Thai and English names.

### Data Pipeline

```
Google Sheet CSV (registry)                Scraper (daily via GitHub Actions)
  เอเจ้นหาปลา - working sheet.csv           data/scripts/scraper.py
           │                                          │
           └──── fallback for failed sources ─────────┤
                                                      ▼
                                          data/raw/seafood_prices.csv
                                                      │
                                                      ▼
                                             data/loader.py
                                          (unified data layer)
                                                      │
                              ┌────────────┬──────────┼──────────┐
                              ▼            ▼          ▼          ▼
                         agent/tools   dashboard  shop_profile  chat
```

The scraper runs daily at 8:00 AM Bangkok time via GitHub Actions. It visits known product URLs from the registry, extracts current prices, and appends timestamped rows to `seafood_prices.csv`. History is kept for the last 30 scrape dates to support price trend analysis.

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

# 6. Run the scraper to get fresh price data
python data/scripts/scraper.py          # full scrape (~3 min)
python data/scripts/scraper.py --test   # quick test (1 URL per site)

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
5. Daily price updates are handled by GitHub Actions — the workflow commits fresh data to the repo, and Streamlit Cloud auto-redeploys.

## Vibe-Coding Tools Used

| Tool | Used For |
|------|----------|
| Claude Code (CLI) | Agent architecture design, code generation, scraper development, project planning, debugging |
| Claude (claude.ai) | System prompt iteration, bilingual prompt engineering |

## Known Limitations

- HENG HENG Seafood uses JS-rendered pricing that can't be scraped via BeautifulSoup — falls back to static registry data from the Google Sheet
- Login is a single shared password (sufficient for class demo; swap to per-user auth before production)
- Price trend requires 2+ days of scrape history — first day shows cross-shop price spread as fallback
- `calculate_order_cost` tool is on a feature branch (not yet merged to main)

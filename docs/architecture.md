# Agent Architecture

## Overview

The Bangkok Seafood Price Advisor uses a **LangGraph ReAct agent** with a feedback loop for iterative tool calling. The agent reasons over user questions in Thai or English, calls tools to query real scraped price data from 7 Bangkok seafood shops, and synthesises bilingual recommendations with product links.

## Agent Graph

```
User Question (e.g. "เปรียบเทียบราคากุ้งลายเสือทุกร้าน")
        │
        ▼
┌──────────────────┐
│     START         │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│   Agent Node     │◄───────────────────┐
│  (Claude Sonnet  │                    │
│   4.5 + Tools)   │                    │
└────────┬─────────┘                    │
         │                              │
┌────────▼─────────┐                    │
│   Condition:     │                    │
│   tool_calls?    │                    │
└───┬──────────┬───┘                    │
    │YES       │NO                      │
    ▼          ▼                        │
┌────────┐  ┌─────┐                    │
│ Tool   │  │ END │                    │
│ Node   │  └─────┘                    │
└───┬────┘                              │
    └───────────────────────────────────┘
         (results fed back to agent)
```

The agent may call multiple tools in a single turn (e.g. `query_seafood_prices` then `get_best_deals`) before formulating a final response. This ReAct loop is visible in the Streamlit UI via the **Tool calls** expander.

## Components

### LLM Core
- **Model**: Anthropic Claude Sonnet 4.5 via `ChatAnthropic` (LangChain)
- **Temperature**: 0 (deterministic for reliable tool calling)
- **Tool binding**: LLM is bound to all tools via `.bind_tools()`
- **Bilingual**: System prompt instructs the agent to respond in the same language the user writes in

### Tools

| Tool | Input | Output | Implementation |
|------|-------|--------|----------------|
| `query_seafood_prices` | item, shop? | Formatted price table with links | Pandas query on CSV, bilingual search |
| `get_best_deals` | category? | Top 5 deals below market avg | Cross-shop price comparison |
| `get_price_trend` | item, days? | Date × shop price table or spread | Historical or snapshot fallback |
| `calculate_order_cost` | items, shop? | Grand total with transport fee | *(feature branch)* |

Tools are registered via LangChain `@tool` decorator with auto-schema generation. Search works across English names, Thai names (`group_th`), website names (`item_name_website`), and category names in both languages.

### State Management
- **`AgentState(TypedDict)`**: Contains `messages` list
- Messages accumulate across the conversation (full history preserved)
- System prompt injected as first message

### Data Pipeline

```
Registry CSV (Google Sheet export)         Daily Scraper (GitHub Actions)
  เอเจ้นหาปลา - working sheet.csv           data/scripts/scraper.py
  ~229 products from 7 shops                 Runs 8am BKK daily
           │                                          │
           │ fallback for failed sources              │ appends timestamped rows
           │ (e.g. HENG HENG Seafood)                 │
           ▼                                          ▼
                        data/loader.py
                   (unified data layer)
                   load_seafood_data()
                            │
                    merges scraped + registry
                    for complete coverage
                            │
              ┌─────────────┼─────────────┐
              ▼             ▼             ▼
         agent/tools   dashboard.py  shop_profile.py
```

**Schema**: `scrape_date | source | item_name_website | group_en | group_th | option | weight_kg | selling_price | price_per_kg | link`

**Scraper architecture**:
- Registry-driven: visits known product URLs from the Google Sheet CSV
- WooCommerce parser: extracts per-variant prices from `data-product_variations` JSON (6 sites)
- Page365 parser: direct JSON API response (Supreme Seafoods)
- Fallback: when a source can't be scraped (e.g. JS-rendered pricing), the registry's static data is used
- History: retains last 30 scrape dates; older data is trimmed automatically

### Observability
- **Langfuse `CallbackHandler`**: auto-traces every LLM call, tool invocation, token usage
- Graceful fallback if Langfuse credentials not set (agent runs without tracing)
- **Streamlit tool panel**: each assistant reply has an expandable section showing which tools were called and their raw output

### User Interface (Streamlit)

| Page | File | Description |
|------|------|-------------|
| Chat | `app/pages/chat.py` | ReAct agent chatbot with bilingual example prompts |
| Price Dashboard | `app/pages/dashboard.py` | Category filter, decision card, price comparison charts, shop pivot table |
| Shop Profiles | `app/pages/shop_profile.py` | Per-shop report card with KPIs, price positioning, product catalog |

All pages are protected by a shared password gate (`app/auth.py`). Product links in chat responses and dashboard tables are clickable, linking to the shop's product page.

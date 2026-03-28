# Bangkok Seafood Price Advisor — Agentic AI

> MADT 7204 Vibe Coding Project | Bangkok Oil Price Crisis

## Team

| Role | Name |
|------|------|
| IT Lead | [Your Name] |
| Mgmt Member | [Member 1] |
| Mgmt Member | [Member 2] |
| Mgmt Member | [Member 3] |
| Mgmt Member | [Member 4] |
| Mgmt Member | [Member 5] |

## Problem Statement

Thailand's oil price crisis has driven up fuel and cold-chain logistics costs, making seafood prices volatile across Bangkok markets. Restaurants, wholesalers, and households struggle to find the best deals as prices shift daily across vendors.

This agent solves that by scraping daily seafood prices from multiple Bangkok markets, comparing them across shops and SKUs, and recommending where to buy — saving time and money for anyone purchasing seafood in bulk.

## Agent Design

This project uses a **LangGraph ReAct agent** with a tool-calling feedback loop and **Langfuse** for full observability.

- **Framework**: LangGraph (graph-based agent with cycles)
- **LLM**: Gemini 2.0 Flash (via LangChain)
- **Observability**: Langfuse (self-hosted, auto-tracing every LLM call and tool use)
- **UI**: Streamlit (planned Week 4)

### How It Works

```
User asks: "Compare shrimp prices across all shops today"
  → Agent reasons about the question
  → Calls compare_prices tool with item="shrimp"
  → Tool queries the price database (Pandas on CSV)
  → Returns ranked results to the LLM
  → Agent formulates a recommendation
  → User sees: best price, price spread, availability
```

### Tools

| Tool | Description |
|------|-------------|
| `query_seafood_prices` | Query prices by item, shop, and date |
| `compare_prices` | Compare a specific item across all shops, ranked by price |

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
# Edit .env with your Google API key and Langfuse credentials

# 5. Generate sample data
python data/scripts/generate_sample_data.py

# 6. Run the agent (CLI)
python -m agent.main
```

## Vibe-Coding Tools Used

| Tool | Used For |
|------|----------|
| Claude Code | Agent architecture scaffolding, code generation, project planning |

## Known Limitations

- Currently uses synthetic sample data (real scraping in Week 2)
- CLI-only interface (Streamlit UI planned for Week 4)
- 2 tools implemented (more planned: availability check, price trends, order cost calculator)

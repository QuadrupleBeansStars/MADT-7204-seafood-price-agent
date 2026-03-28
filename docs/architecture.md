# Agent Architecture

## Overview

The Bangkok Seafood Price Advisor uses a **LangGraph ReAct agent** with a feedback loop for iterative tool calling. The agent reasons over user questions, calls tools to query real price data, and synthesizes recommendations.

## Agent Graph

```
User Question (e.g. "Compare shrimp prices across shops today")
        │
        ▼
┌──────────────────┐
│     START         │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│   Agent Node     │◄───────────────────┐
│  (Gemini 2.0     │                    │
│   Flash + Tools) │                    │
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

## Components

### LLM Core
- **Model**: Gemini 2.0 Flash via `ChatGoogleGenerativeAI` (LangChain)
- **Temperature**: 0 (deterministic for reliable tool calling)
- **Tool binding**: LLM is bound to all tools via `.bind_tools()`

### Tools

| Tool | Input | Output | Implementation |
|------|-------|--------|----------------|
| `query_seafood_prices` | item, shop?, date? | Formatted price table | Pandas query on CSV |
| `compare_prices` | item, date? | Ranked price comparison | Pandas sort + format |

Tools are registered via LangChain `@tool` decorator with auto-schema generation.

### State Management
- **`AgentState(TypedDict)`**: Contains `messages` list
- Messages accumulate across the conversation (full history preserved)
- System prompt injected as first message

### Data Pipeline

```
data/scripts/scraper.py      ← daily scrape (skeleton, real targets TBD)
data/scripts/generate_sample_data.py  ← synthetic data for dev
        │
        ▼
data/raw/seafood_prices_sample.csv
        │
        ▼
agent/tools/seafood_prices.py  ← Pandas reads CSV, returns formatted strings
```

**Schema**: `date | shop | sku | item_name | category | price_per_kg | unit | available`

### Observability
- **Langfuse `CallbackHandler`**: auto-traces every LLM call, tool invocation, token usage
- Self-hosted Langfuse instance
- Graceful fallback if Langfuse credentials not set

## Planned Enhancements
- [ ] Multi-agent: planner delegates to price agent + availability agent
- [ ] More tools: availability check, price trends, order cost calculator
- [ ] RAG: vector store over government subsidy/policy documents
- [ ] Memory: LangGraph checkpointer for cross-turn context
- [ ] Agentic retry: auto-retry on failed tool calls
- [ ] Streamlit UI with reasoning trace panel

# App Usage Guide — Chatbot, Dashboards, and Tool Reference

This page is the cheat sheet for demoing the Bangkok Seafood Price Advisor. It covers the three UI surfaces — **Chat** (the agent), **Price Dashboard**, and **Shop Profiles** — and shows which questions the agent answers with which tool. Each section links back to the `TASK_XX_*.md` brief the feature was built from so reviewers can see the work → deliverable lineage.

| Feature | Delivered by | Task brief |
|---|---|---|
| `query_seafood_prices` tool | scaffold | — (baseline tool) |
| `get_best_deals` tool | agent | [`tasks/TASK_03_best_deals.md`](../tasks/TASK_03_best_deals.md) |
| `get_price_trend` tool | agent | [`tasks/TASK_02_price_trend.md`](../tasks/TASK_02_price_trend.md) |
| `calculate_order_cost` tool *(in-flight)* | agent | [`tasks/TASK_01_order_cost.md`](../tasks/TASK_01_order_cost.md) |
| 📊 Price Dashboard page | UI | [`tasks/TASK_04_dashboard.md`](../tasks/TASK_04_dashboard.md) |
| 🏪 Shop Profile page | UI | [`tasks/TASK_05_shop_profile.md`](../tasks/TASK_05_shop_profile.md) |

---

## 1. Chat (agent loop)

The main page (`app/pages/chat.py`, dispatched by the `app/main.py` orchestrator) is a chat backed by a **LangGraph ReAct agent** running on **Claude Sonnet 4.5**. Each turn, Claude decides whether to reply directly or call one of the tools below. You can watch it happen live by expanding the **🔧 Used N tool(s)** panel at the bottom of each assistant reply.

### Data source

The agent queries **real product data** scraped from 7 Bangkok seafood e-commerce websites:

| Shop | Products |
|---|---|
| ไต้ก๋ง ซีฟู้ด (Taikong Seafood) | 30 |
| Sawasdee Seafood | 18 |
| HENG HENG Seafood | 46 |
| PPNSeafood | 55 |
| supreme seafoods | 44 |
| siriratseafood | 26 |
| sirinfarm | 10 |

Products are grouped into 5 categories: **shrimp (กุ้ง)**, **fish (ปลา)**, **squid (หมึก)**, **crab (ปู)**, **shellfish (หอย/เปลือก)**.

### Bilingual support

The agent responds in the same language the user writes in. Thai questions get Thai answers; English questions get English answers. Product names always include both Thai and English — e.g. "กุ้งลายเสือ (Tiger Prawn)".

### Quickstart

- **First visit**: the page shows 4 example-prompt chips (2 Thai, 2 English). Click one to fire the agent without typing.
- **🧹 Clear chat history** (sidebar): resets the conversation so demos start clean without a full logout/login cycle.
- **Spinner**: while Claude is thinking, you'll see *"🐟 Consulting Bangkok markets…"* — so nothing ever looks frozen.

### Tools available to the agent

#### 1.1 `query_seafood_prices(item, shop?)` — baseline lookup

| Arg | Required | Example | Notes |
|---|---|---|---|
| `item` | yes | `"shrimp"`, `"salmon"`, `"กุ้ง"`, `"ปลาแซลมอน"` | Searches across English name, Thai name, and category |
| `shop` | no | `"PPNSeafood"`, `"ไต้ก๋ง"` | Partial, case-insensitive match on source |

Fires when the user asks about a **specific item**, usually narrowed to a shop. Returns prices with product options/sizes and clickable links to the shop's product page.

| Prompt (EN) | Prompt (TH) |
|---|---|
| *"How much is tiger prawn?"* | *"กุ้งลายเสือราคาเท่าไหร่?"* |
| *"What's the price of salmon at PPNSeafood?"* | *"ปลาแซลมอนที่ PPNSeafood ราคาเท่าไหร่?"* |
| *"Show me grouper prices"* | *"ราคาปลาเก๋าทุกร้าน"* |

---

#### 1.2 `get_best_deals(category?)` → TASK_03

> Connects to [`tasks/TASK_03_best_deals.md`](../tasks/TASK_03_best_deals.md) — the "morning market summary" ask.

Returns up to 5 items priced >10% below the cross-shop market average, sorted by biggest discount. Includes product links.

| Arg | Required | Example | Notes |
|---|---|---|---|
| `category` | no | `"shrimp"`, `"fish"`, `"กุ้ง"`, `"ปลา"` | Accepts English or Thai category names |

Fires on **deal / bargain / discount / "what should I buy today"** prompts.

| Prompt (EN) | Prompt (TH) |
|---|---|
| *"What are today's best seafood deals?"* | *"วันนี้ซีฟู้ดอะไรดีลเด็ดบ้าง?"* |
| *"Any bargain shrimp right now?"* | *"มีกุ้งลดราคาอยู่ไหม?"* |
| *"Show me discounts on fish."* | *"ปลาตัวไหนราคาดีที่สุด?"* |

---

#### 1.3 `get_price_trend(item, days=7)` → TASK_02

> Connects to [`tasks/TASK_02_price_trend.md`](../tasks/TASK_02_price_trend.md) — the "buy now or wait" ask.

When historical scrape data exists (multiple daily scrapes), returns a date × shop price table with trend summary. When only snapshot data is available, shows the **current price spread across shops** as a useful fallback.

| Arg | Required | Example | Notes |
|---|---|---|---|
| `item` | yes | `"salmon"`, `"crab"`, `"หมึก"` | Partial, case-insensitive; accepts Thai |
| `days` | no | `7`, `14`, `30` | Defaults to 7 |

Fires on **history / trend / direction / timing / comparison** prompts.

| Prompt (EN) | Prompt (TH) |
|---|---|
| *"Compare salmon prices across all shops"* | *"เปรียบเทียบราคาแซลมอนทุกร้าน"* |
| *"Show me the price spread for squid."* | *"ดูราคาหมึกทุกร้าน"* |
| *"Is now a good time to buy crab?"* | *"ตอนนี้ซื้อปูคุ้มไหม?"* |

---

#### 1.4 `calculate_order_cost(items, shop?)` — *pending merge* → TASK_01

> Connects to [`tasks/TASK_01_order_cost.md`](../tasks/TASK_01_order_cost.md). Lives on `feature/calculate_order_cost_tool` — not yet in main.

Once merged, it takes a shopping list string (`"tiger prawn:2, sea bass:1"`) and returns the per-shop grand total including a **transport fee with an oil surcharge**.

| Prompt (EN) | Prompt (TH) |
|---|---|
| *"I need 2kg tiger prawn and 1kg sea bass — which shop is cheapest?"* | *"ฉันต้องการกุ้งลายเสือ 2 กก. และปลากะพง 1 กก. ร้านไหนถูกที่สุด?"* |

### Source links and order buttons

Every tool response includes **clickable product links** to the shop's website. When the agent gives a recommendation, it ends with an **order summary table**:

| สินค้า (Product) | ร้าน (Shop) | ราคา (Price) | สั่งซื้อ (Order) |
|---|---|---|---|
| กุ้งลายเสือ XL (Tiger Prawn) | ไต้ก๋ง ซีฟู้ด | ฿850/kg | [สั่งซื้อ](https://taikongseafood.com/product/tiger-prawn/) |

Clicking "สั่งซื้อ" opens the shop's product page in a new tab.

### Multi-step use cases (tool chaining)

These prompts make the agent call more than one tool in a single turn — the strongest demo of the ReAct loop.

**A. "Is the cheapest really a deal?"** (exercises TASK_03 + baseline)
> *"เปรียบเทียบราคากุ้งลายเสือทุกร้าน แล้วบอกว่าร้านที่ถูกที่สุดเป็นดีลจริงไหม"*

Expected: `query_seafood_prices(item="กุ้งลายเสือ")` → `get_best_deals(category="shrimp")` → synthesized verdict.

**B. "Should I wait?"** (exercises TASK_02 + baseline)
> *"Salmon looks expensive at PPNSeafood. How does it compare to other shops?"*

Expected: `query_seafood_prices(item="salmon", shop="PPNSeafood")` → `get_price_trend(item="salmon")` → recommendation.

**C. "Build me a mixed basket"** (exercises TASK_03 + baseline)
> *"ฉันต้องสั่งกุ้ง ปลาหมึก และปลากะพง ร้านไหนถูกที่สุดแต่ละอย่าง?"*

Expected: three `query_seafood_prices` calls + one `get_best_deals`.

### Edge cases worth demoing

| Prompt | Why it's interesting |
|---|---|
| *"How much is lobster?"* | Item not in data — agent reports no results, doesn't hallucinate |
| *"Best deal for dragonfruit?"* | Invalid category — agent rejects cleanly |
| *"Show trend for the last 0 days"* | Invalid `days` — tool validates |
| *"กุ้ง"* | Matches all shrimp products via Thai category name |

---

## 2. 📊 Price Dashboard page → TASK_04

> Connects to [`tasks/TASK_04_dashboard.md`](../tasks/TASK_04_dashboard.md). File: `app/pages/dashboard.py`. Reads real data via `data/loader.py` — no LLM, no tool calls.

Target user: a restaurant buyer or wholesaler who wants a **visual, clickable** answer before typing anything to the agent.

**What's on the page**

1. **Category filter** — dropdown to filter by shrimp, fish, squid, crab, shellfish, or all.
2. **🎯 Decision card** — cheapest item per kg across all shops with a direct product link.
3. **Top Insights row (3 metrics)** — cheapest item, premium item, number of shops tracked.
4. **Price comparison chart** — pick a product group from a dropdown, see a bar chart of price per kg across shops and options.
5. **Product comparison & catalog** — multi-select two or more shops to get a side-by-side pivot table (cheapest cell highlighted green), plus the full catalog with clickable product links.

**Typical flow**

> Open dashboard → filter by category → glance at decision card → compare prices in the bar chart → use the pivot table to decide between two shops.

---

## 3. 🏪 Shop Profile page → TASK_05

> Connects to [`tasks/TASK_05_shop_profile.md`](../tasks/TASK_05_shop_profile.md). File: `app/pages/shop_profile.py`. Reads real data via `data/loader.py` — no LLM, no tool calls.

Target user: a buyer evaluating **whether to commit to a supplier** for regular orders — so the page is a per-shop report card, not a comparison view.

**What's on the page**

1. **Sidebar shop selector** — pick any of the 7 real shops (ไต้ก๋ง ซีฟู้ด, PPNSeafood, HENG HENG Seafood, etc.).
2. **Shop report card (4 KPIs)** — product groups count, total items (incl. options/sizes), average price delta vs market, categories covered.
3. **Tab: Price Positioning** — bar chart comparing this shop's average price vs the market average, per product group.
4. **Tab: Product Range** — pie chart of category distribution + price range bar chart per product group.
5. **Tab: Full Catalog** — complete product list with options/sizes, prices, and clickable product links.

**Typical flow**

> Pick shop → read the 4 KPIs → check positioning chart to see if they're above/below market → browse the catalog to see options and click through to order.

---

## 4. Demo tips

- Always open the **🔧 Tool calls** expander on the first chat message — audience sees the ReAct loop.
- For the chatbot, lead with a multi-step prompt (A / B / C above) — single-tool questions are less impressive.
- Start with a **Thai prompt** to show bilingual capability — it's a strong visual.
- The dashboards are the fallback for non-technical viewers who don't want to type.
- Product links in chat responses and dashboard tables are clickable — demo clicking through to a real shop.
- With `temperature=0`, the same question repeated should pick the same tools — useful for a deterministic live demo.

---

## 5. Reverse lookup: "which task does this demo?"

| If the demo shows… | …it's exercising |
|---|---|
| Deal hunting in chat | TASK_03 → `get_best_deals` |
| Price spread / comparison in chat | TASK_02 → `get_price_trend` (snapshot fallback) |
| Multi-item grand total in chat | TASK_01 → `calculate_order_cost` *(pending merge)* |
| Decision card + price comparison chart | TASK_04 → dashboard page |
| Per-shop report card / positioning / catalog | TASK_05 → shop profile page |
| Baseline item lookup ("price of X at Y") | Scaffold `query_seafood_prices` |
| Order links / source links in chat | System prompt + tool output formatting |
| Thai language support | Bilingual system prompt + Thai-aware search |

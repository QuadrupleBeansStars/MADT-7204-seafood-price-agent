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

### Quickstart

- **First visit**: the page shows 4 example-prompt chips (deals / price lookup / trend / multi-step). Click one to fire the agent without typing.
- **🧹 Clear chat history** (sidebar): resets the conversation so demos start clean without a full logout/login cycle.
- **Spinner**: while Claude is thinking, you'll see *"🐟 Consulting Bangkok markets…"* — so nothing ever looks frozen.

### Tools available to the agent

#### 1.1 `query_seafood_prices(item, shop?, target_date?)` — baseline lookup

| Arg | Required | Example | Notes |
|---|---|---|---|
| `item` | yes | `"shrimp"`, `"salmon"`, `"squid"` | Case-insensitive partial match on `item_name` |
| `shop` | no | `"Makro"`, `"Talad Thai"` | Partial, case-insensitive |
| `target_date` | no | `"2026-04-16"` | ISO date. Defaults to the most recent date |

Fires when the user asks about a **specific item**, usually narrowed to a shop or date.

| Prompt (EN) | Prompt (TH) |
|---|---|
| *"How much is white shrimp today?"* | *"วันนี้กุ้งขาวราคาเท่าไหร่?"* |
| *"What's the price of salmon at Makro?"* | *"ปลาแซลมอนที่ Makro ราคาเท่าไหร่?"* |
| *"Snapper at Or Tor Kor on 2026-04-10?"* | *"ราคาปลากะพงที่ อ.ต.ก. เมื่อ 10 เม.ย.?"* |

---

#### 1.2 `get_best_deals(category?, target_date?)` → TASK_03

> Connects to [`tasks/TASK_03_best_deals.md`](../tasks/TASK_03_best_deals.md) — the "morning market summary" ask.

Returns up to 5 items priced >10% below the cross-shop market average, sorted by biggest discount.

| Arg | Required | Example | Notes |
|---|---|---|---|
| `category` | no | `"shrimp"`, `"fish"`, `"squid"`, `"crab"`, `"shellfish"` | Must match one of the 5 categories |
| `target_date` | no | `"2026-04-16"` | Defaults to latest date |

Fires on **deal / bargain / discount / "what should I buy today"** prompts.

| Prompt (EN) | Prompt (TH) |
|---|---|
| *"What are today's best seafood deals?"* | *"วันนี้ซีฟู้ดอะไรดีลเด็ดบ้าง?"* |
| *"Any bargain shrimp right now?"* | *"มีกุ้งลดราคาอยู่ไหม?"* |
| *"Show me discounts on fish today."* | *"ปลาตัวไหนราคาดีที่สุดวันนี้?"* |

---

#### 1.3 `get_price_trend(item, days=7)` → TASK_02

> Connects to [`tasks/TASK_02_price_trend.md`](../tasks/TASK_02_price_trend.md) — the "buy now or wait" ask.

Returns a date × shop price table plus a summary of which shop rose most / dropped most over the window.

| Arg | Required | Example | Notes |
|---|---|---|---|
| `item` | yes | `"salmon"`, `"crab"` | Partial, case-insensitive |
| `days` | no | `7`, `14`, `30` | Defaults to 7 |

Fires on **history / trend / direction / timing** prompts.

| Prompt (EN) | Prompt (TH) |
|---|---|
| *"Has salmon gone up this week?"* | *"ปลาแซลมอนแพงขึ้นไหมอาทิตย์นี้?"* |
| *"Show me the 7-day price trend for squid."* | *"ดูแนวโน้มราคาปลาหมึก 7 วัน"* |
| *"Is now a good time to buy crab?"* | *"ตอนนี้ซื้อปูคุ้มไหม?"* |

---

#### 1.4 `calculate_order_cost(items, shop?)` — *pending merge* → TASK_01

> Connects to [`tasks/TASK_01_order_cost.md`](../tasks/TASK_01_order_cost.md). Lives on `feature/calculate_order_cost_tool` — not yet in main.

Once merged, it takes a shopping list string (`"white shrimp:2, sea bass:1"`) and returns the per-shop grand total including a **transport fee with an oil surcharge** — the project's core business insight (fuel costs ripple into delivery, not just seafood prices).

Will fire on **shopping list / grand total / "cheapest shop for my order"** prompts.

| Prompt (EN) | Prompt (TH) |
|---|---|
| *"I need 2kg white shrimp and 1kg sea bass — which shop is cheapest total?"* | *"ฉันต้องการกุ้งขาว 2 กก. และปลากะพง 1 กก. ร้านไหนถูกที่สุด?"* |
| *"Quote me 5kg white shrimp + 2kg snapper delivered from Makro."* | *"ขอใบเสนอราคากุ้งขาว 5 กก. + ปลากะพง 2 กก. ส่งจาก Makro"* |

### Multi-step use cases (tool chaining)

These prompts make the agent call more than one tool in a single turn — the strongest demo of the ReAct loop.

**A. "Is the cheapest really a deal?"** (exercises TASK_03 + baseline)
> *"Compare white shrimp across all shops today and tell me if the cheapest one is a genuine deal or just normal pricing."*

Expected: `query_seafood_prices(item="white shrimp")` → `get_best_deals(category="shrimp")` → synthesized verdict.

**B. "Should I wait?"** (exercises TASK_02 + baseline)
> *"Snapper looks expensive at Talad Thai. Is that a short-term spike or has it been like this all week?"*

Expected: `query_seafood_prices(item="snapper", shop="Talad Thai")` → `get_price_trend(item="snapper", days=7)` → buy/wait recommendation.

**C. "Build me a mixed basket"** (exercises TASK_01 once merged; TASK_03 + baseline meanwhile)
> *"I need to order shrimp, squid, and sea bass for tomorrow. Which shop is cheapest for each, and are any of them on sale?"*

Expected today: three `query_seafood_prices` calls + one `get_best_deals`.
Expected after TASK_01 merges: one `calculate_order_cost` call.

### Edge cases worth demoing

| Prompt | Why it's interesting |
|---|---|
| *"How much is lobster?"* | Item not in data — agent reports no results, doesn't hallucinate |
| *"What are tomorrow's prices?"* | Future date — no data available |
| *"Best deal for dragonfruit?"* | Invalid category — agent rejects cleanly |
| *"Show trend for the last 0 days"* | Invalid `days` — tool validates |

---

## 2. 📊 Price Dashboard page → TASK_04

> Connects to [`tasks/TASK_04_dashboard.md`](../tasks/TASK_04_dashboard.md). File: `app/pages/dashboard.py`. Reads the CSV directly — no LLM, no tool calls.

Target user: a restaurant buyer or wholesaler who wants a **visual, clickable** answer before typing anything to the agent.

**What's on the page**

1. **🎯 Decision card** — today's cheapest in-stock item with shop name and per-kg price, framed as a "buy now" call-out.
2. **Top Insights row (3 metrics)** — cheapest item today, biggest price drop vs the previous date, biggest price spike vs the previous date.
3. **Price trend analysis** — pick an item from a dropdown, see a 30-day area chart per shop, plus an action verdict (BUY NOW / WAIT / ALTERNATIVE) derived from where today's price sits within the min/max window.
4. **Product comparison & catalog** — multi-select two or more shops to get a side-by-side pivot table (cheapest cell highlighted green), plus the full latest-day catalog with availability checkboxes.

**Typical flow**

> Open dashboard → glance at decision card → check drop/spike metrics → dive into the trend chart for the item you care about → compare the two suppliers you're deciding between in the pivot table.

---

## 3. 🏪 Shop Profile page → TASK_05

> Connects to [`tasks/TASK_05_shop_profile.md`](../tasks/TASK_05_shop_profile.md). File: `app/pages/shop_profile.py`. Reads the CSV directly — no LLM, no tool calls.

Target user: a buyer evaluating **whether to commit to a supplier** for regular orders — so the page is a per-shop report card, not a comparison view.

**What's on the page**

1. **Sidebar shop selector** — pick any of the 5 shops.
2. **Shop report card (4 KPIs)** — total SKUs stocked, stock availability rate (% of rows marked available across the window), average price delta vs market average, and the last-updated date.
3. **Tab: Price Positioning** — bar chart comparing this shop's price vs the market average, per item, for today.
4. **Tab: Price History** — pick an item, see this shop's price over time.
5. **Tab: Inventory Detail** — today's full item list at this shop with price and availability.

**Typical flow**

> Pick shop → read the 4 KPIs for a quick trust read → check positioning chart to see whether they're consistently above/below market → use history tab to check an item you're about to order.

---

## 4. Demo tips

- Always open the **🔧 Tool calls** expander on the first chat message — audience sees the ReAct loop.
- For the chatbot, lead with a multi-step prompt (A / B / C above) — single-tool questions are less impressive.
- The dashboards are the fallback for non-technical viewers who don't want to type.
- Thai-language chat works — Claude Sonnet 4.5 handles Thai item names and shop names fine.
- With `temperature=0`, the same question repeated should pick the same tools — useful for a deterministic live demo.

---

## 5. Reverse lookup: "which task does this demo?"

| If the demo shows… | …it's exercising |
|---|---|
| Deal hunting in chat | TASK_03 → `get_best_deals` |
| "Going up or down?" in chat | TASK_02 → `get_price_trend` |
| Multi-item grand total in chat | TASK_01 → `calculate_order_cost` *(pending merge)* |
| Decision card + trend chart with BUY/WAIT verdict | TASK_04 → dashboard page |
| Per-shop report card / positioning / history | TASK_05 → shop profile page |
| Baseline item lookup ("price of X at Y") | Scaffold `query_seafood_prices` (no task brief — shipped with the initial scaffold) |

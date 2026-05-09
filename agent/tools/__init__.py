from agent.tools.oil_briefing import generate_oil_briefing
from agent.tools.oil_context import get_oil_context, oil_snapshot_line
from agent.tools.seafood_prices import (
    get_best_deals,
    get_price_trend,
    query_seafood_prices,
)
from agent.tools.talaadthai_benchmark import get_talaadthai_benchmark

ALL_TOOLS = [
    query_seafood_prices,
    get_best_deals,
    get_price_trend,
    get_talaadthai_benchmark,
    get_oil_context,
    generate_oil_briefing,
]

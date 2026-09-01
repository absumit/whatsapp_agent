"""Shared price-resolution logic used by both calculate_order_price and update_order."""

from core import db
from numbers import Real

from core.schemas import order_item


def resolve_price(item: order_item):
    if not db.cached_menu:
        return None, "Menu pricing is currently unavailable"

    fetched_items = None
    for val in db.cached_menu:
        if val["category"] == item.catg:
            fetched_items = val["items"]
            break

    if fetched_items is None:
        return None, f"{item.catg} is not a valid category"

    for val in fetched_items:
        if val["name"] == item.item_name:
            prices = val["prices"]
            price = prices.get(item.portion)
            if price is None:
                return None, f"{item.item_name} has no '{item.portion}' option — available: {list(prices.keys())}"
            if not isinstance(price, Real) or isinstance(price, bool):
                return None, f"{item.item_name} has a market price and cannot be calculated automatically"
            return float(price), None

    return None, f"{item.item_name} not found in {item.catg}"
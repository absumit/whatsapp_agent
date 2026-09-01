import os
from dotenv import load_dotenv
from core import db
from core.schemas import order_item, order_request, CategoryLiteral
from core.pricing import resolve_price
from langchain_core.tools import tool
from typing import List
load_dotenv()

front_menu = os.getenv("MENU_URL_FRONT")
back_menu = os.getenv("MENU_URL_BACK")


@tool
def get_menu():
    """Get menu photo links and category when the user asks to see the menu."""
    category = list(CategoryLiteral.__args__)
    menu_links = {"menu_front": front_menu, "menu_back": back_menu}
    return category, menu_links


@tool
def get_category_pricing(category: CategoryLiteral):
    """Get all item detail (pricing, quantity) for a category from the database."""
    try:
        if db.cached_menu:
            for value in db.cached_menu:
                if value["category"] == category:
                    return value["items"]

        if db.menu_collection is None:
            return "Menu database is unavailable."

        results = list(db.menu_collection.find(
            {"category": category},
            {"_id": 0}
        ))
        return results or f"No items found in {category}"

    except Exception as error:
        print(f"Failed to get category pricing: {error}")
        return "Problem loading menu pricing."


@tool(args_schema=order_request)
def calculate_order_price(items: List[order_item]):
    """Calculate the total price of the user's order. Pass each item's category, exact item name, quantity, and portion."""
    print("price calculation executed")
    total = 0
    for item in items:
        price, error = resolve_price(item)
        if error:
            return error
        total += price * item.quantity
    return total
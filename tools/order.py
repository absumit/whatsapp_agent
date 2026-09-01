from typing import Annotated, List
from langchain_core.messages import ToolMessage
from langchain_core.tools import tool, InjectedToolCallId
from langgraph.prebuilt import InjectedState
from langgraph.types import Command
from core.schemas import order_item, order_request, OrderState, cart_line
from core.pricing import resolve_price


@tool(args_schema=order_request)
def update_order(
    items: List[order_item],
    state: Annotated[OrderState, InjectedState],
    tool_call_id: Annotated[str, InjectedToolCallId],
) -> Command:
    """Add ordered items to the user's cart."""
    print("update order executed")
    print(f"DEBUG cart on entry to update_order: {state.get('cart', [])}")

    new_lines = []
    for item in items:
        price, error = resolve_price(item)
        if error:
            return Command(update={
                "messages": [ToolMessage(error, tool_call_id=tool_call_id)]
            })
        new_lines.append(cart_line(**item.model_dump(), price=price))

    updated_cart = state.get("cart", []) + new_lines
    total_so_far = sum(line.price * line.quantity for line in updated_cart)

    return Command(update={
        "cart": updated_cart,
        "messages": [ToolMessage(
            f"Added to order. Cart: {updated_cart} | Running total: ₹{total_so_far}",
            tool_call_id=tool_call_id
        )]
    })
"""Single source of truth for Pydantic models and graph state used across all tools."""

from typing import Annotated, List, Literal, TypedDict
from pydantic import BaseModel, Field
from langgraph.graph import add_messages

CategoryLiteral = Literal[
    "SOUTH INDIAN", "CHAPATI / RICE", "ROLLS", "MOMOS", "DESERT",
    "FRIED RICE", "NOODLES", "CHILLI", "INDIAN", "THALI / BIRYANI"
]


class order_item(BaseModel):
    catg: CategoryLiteral
    item_name: str = Field(description="exact item name as it appears in the menu")
    quantity: int = Field(gt=0, le=100, description="number of units ordered")
    portion: str = Field(
        default="full",
        description="serving size if applicable — 'half' or 'full'. Default to 'full' if the item only has one size."
    )


class order_request(BaseModel):
    items: List[order_item] = Field(min_length=1, max_length=50, description="All items the user wants to order")


class cart_line(order_item):
    price: float = Field(description="unit price resolved from menu DB, never LLM-supplied")


class OrderState(TypedDict):
    messages: Annotated[list, add_messages]
    cart: List[cart_line]
    phone_number: str
    customer_name: str
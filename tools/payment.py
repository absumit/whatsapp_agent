"""LangChain wrappers for payment operations."""
import os
from dotenv import load_dotenv
import razorpay
import time
from typing import Annotated
from langchain_core.tools import tool, InjectedToolCallId
from langgraph.prebuilt import InjectedState
from langgraph.types import Command
from langchain_core.messages import ToolMessage

from core.schemas import OrderState
from core.db import orders_collection

load_dotenv()

RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID")
RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET")
RAZORPAY_WEBHOOK_SECRET = os.getenv("RAZORPAY_WEBHOOK_SECRET")
RAZORPAY_API_BASE = "https://api.razorpay.com/v1"

if not RAZORPAY_KEY_ID or not RAZORPAY_KEY_SECRET:
    raise RuntimeError("RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET are required")

client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))



def create_link(amount: int, reference_id: str,expire_min: int=20 ):
    expire_by = int(time.time()) + (expire_min * 60)
    link_details = client.payment_link.create({
        "amount": amount * 100,
        "currency": "INR",
         "expire_by": expire_by,
        "reference_id": reference_id,
        "callback_url": "https://wa.me/14155238886?text=paid",
        "callback_method": "get",
    })
    return link_details


@tool
def generate_payment_link(
    state: Annotated[OrderState, InjectedState],
    tool_call_id: Annotated[str, InjectedToolCallId],
) -> Command:
    """Generate a Razorpay payment link for the user's current cart and send it to them."""

    cart = state.get("cart", [])
    phone = state.get("phone_number", "")
    customer_name = state.get("customer_name", "")

    if not cart:
        return Command(update={
            "messages": [ToolMessage("Your cart is empty — add some items first.", tool_call_id=tool_call_id)]
        })

    # ---- NEW: cancel any still-outstanding old links for this customer first ----
    old_pending = orders_collection.find({
        "phone": phone,
        "status": "payment_pending",
        "razorpay_payment_link_id": {"$exists": True},
    })
    for old_order in old_pending:
        try:
            client.payment_link.cancel(old_order["razorpay_payment_link_id"])
        except Exception as e:
            print(f"failed to cancel old link {old_order['razorpay_payment_link_id']}: {e}")
        orders_collection.update_one(
            {"_id": old_order["_id"]},
            {"$set": {"status": "cancelled", "cancelled_reason": "superseded_by_new_link"}}
        )
    # ------------------------------------------------------------------------------

    total_rupees = sum(val.price * val.quantity for val in cart)

    description = ""
    for val in cart:
        description += f"{val.quantity}x {val.item_name} ({val.portion}), "

    order_doc = {
        "phone": phone,
        "customer_name": customer_name,
        "amount_rupees": total_rupees,
        "description": description,
        "cart": [val.model_dump() for val in cart],
        "status": "payment_pending",
    }
    inserted = orders_collection.insert_one(order_doc)
    reference_id = inserted.inserted_id

    try:
        link_details = create_link(total_rupees, str(reference_id))
    except Exception:
        orders_collection.update_one(
            {"_id": reference_id},
            {"$set": {"status": "payment_failed"}},
        )
        raise
    short_url = link_details["short_url"]
    razorpay_link_id = link_details["id"]

    orders_collection.update_one(
        {"_id": reference_id},
        {"$set": {
            "payment_link_url": short_url,
            "razorpay_payment_link_id": razorpay_link_id,
        }}
    )

    # ---- NEW: this cart has now been "billed" — clear it so future adds start a fresh order ----
    print(f"DEBUG clearing cart, had {len(cart)} items")
    return Command(update={
        "cart": [],
        "messages": [ToolMessage(f"Please complete your payment here: {short_url}", tool_call_id=tool_call_id)]
    })
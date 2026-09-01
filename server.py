import os
import hmac
import hashlib
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor

from dotenv import load_dotenv

load_dotenv()

from flask import Flask, request, jsonify
from twilio.twiml.messaging_response import MessagingResponse
from bson import ObjectId

from core.db import extract_menu, orders_collection
from utils.llm import getmsg
from utils.twilio_client import send_whatsapp

app = Flask(__name__)
executor = ThreadPoolExecutor(max_workers=8)

RAZORPAY_WEBHOOK_SECRET = os.getenv("RAZORPAY_WEBHOOK_SECRET")


def process_message(message: str, phone_number: str, customer_name: str) -> None:
   
    try:
        ai_reply = getmsg(message, phone_number, customer_name)
        send_whatsapp(to=phone_number, body=ai_reply)
        print("message sent to", phone_number)
    except Exception as error:
        print(f"background message failed: {error}")


@app.route("/webhook", methods=["POST"])
def whatsapp_msg():
    in_msg = request.form.get("Body", "")
    ph_num = request.form.get("From", "")
    profile_name = request.form.get("ProfileName", "")
    print("human_msg", in_msg)

    if in_msg and ph_num:
        executor.submit(process_message, in_msg, ph_num, profile_name)

    
    return str(MessagingResponse())


def _verify_webhook_signature(body: bytes, signature: str) -> bool:
    if not RAZORPAY_WEBHOOK_SECRET or not signature:
        return False
    expected = hmac.new(RAZORPAY_WEBHOOK_SECRET.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


@app.route("/razorpay/webhook", methods=["POST"])
def razorpay_webhook():
    signature = request.headers.get("X-Razorpay-Signature", "")
    raw_body = request.get_data()

    if not _verify_webhook_signature(raw_body, signature):
        return jsonify({"error": "invalid signature"}), 400

    payload = request.get_json(silent=True) or {}
    event = payload.get("event", "")
    status_by_event = {
        "payment_link.created": "created",
        "payment_link.paid": "paid",
        "payment_link.cancelled": "cancelled",
        "payment_link.expired": "expired",
    }
    status = status_by_event.get(event)
    if status is None:
        return jsonify({"status": "ignored"}), 200

    link_entity = payload.get("payload", {}).get("payment_link", {}).get("entity", {})
    payment_entity = payload.get("payload", {}).get("payment", {}).get("entity", {})
    reference_id = link_entity.get("reference_id")
    if not reference_id:
        return jsonify({"error": "missing order reference"}), 400

    try:
        order = orders_collection.find_one({"_id": ObjectId(reference_id)})
    except Exception:
        return jsonify({"error": "invalid order reference"}), 400
    if order is None:
        return jsonify({"error": "order not found"}), 404

    if status == "paid" and order.get("status") == "paid" and order.get("payment_confirmation_sent"):
        return jsonify({"status": "already processed"}), 200

    
    if status == "cancelled" and order.get("cancelled_reason") == "superseded_by_new_link":
        return jsonify({"status": "updated", "payment_status": status}), 200
    # -----------------------------------------------------------------------------------------

    now = datetime.now(timezone.utc)
    update = {
        "status": status,
        "razorpay_payment_link_status": link_entity.get("status", status),
        "last_webhook_at": now,
        "last_webhook_event": event,
    }
    if status == "paid":
        update.update({
            "paid_at": order.get("paid_at", now),
            "razorpay_payment_id": payment_entity.get("id"),
            "razorpay_payment_status": payment_entity.get("status"),
        })
    orders_collection.update_one(
        {"_id": order["_id"]},
        {"$set": update}
    )

    if status != "paid":
        return jsonify({"status": "updated", "payment_status": status}), 200

    receipt_lines = "\n".join(
        f"• {item['quantity']}x {item['item_name']} ({item['portion']}) — ₹{item['price'] * item['quantity']}"
        for item in order["cart"]
    )
    receipt_body = (
        f"✅ Payment received — ₹{order['amount_rupees']}\n\n"
        f"{receipt_lines}\n\n"
        f"Thanks for ordering with DunaDakshin!"
    )

    try:
        sid = send_whatsapp(to=order["phone"], body=receipt_body)
        orders_collection.update_one(
            {"_id": order["_id"]},
            {"$set": {
                "payment_confirmation_sent": True,
                "payment_confirmation_sent_at": datetime.now(timezone.utc),
                "payment_confirmation_sid": sid,
            }}
        )
    except Exception as e:
        print(f"failed to send confirmation: {e}")
        orders_collection.update_one(
            {"_id": order["_id"]},
            {"$set": {"payment_confirmation_sent": False}}
        )

    return jsonify({"status": "ok"}), 200

if __name__ == "__main__":
    extract_menu()
    app.run(debug=True, port=5000)
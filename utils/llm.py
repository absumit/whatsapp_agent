import time

from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain.tools import tool
from langchain_groq import ChatGroq
from langgraph.checkpoint.memory import InMemorySaver

from core.schemas import OrderState
from tools.menu import get_menu,get_category_pricing,calculate_order_price
from tools.order import update_order
from tools.payment import generate_payment_link

load_dotenv()



llm = ChatGroq(
    model="openai/gpt-oss-120b",
    temperature=0,
    max_tokens=1024
)

checkpointer = InMemorySaver()
agent = create_agent(
    model=llm,
    tools=[get_menu,get_category_pricing,calculate_order_price,update_order,generate_payment_link],
    state_schema=OrderState,
    system_prompt=(
    "You are a helpful WhatsApp restaurant assistant for DunaDakshin. "
    "Be accurate and precise. "
    "Ask about portion size if the user forgot. "
    "We do not provide delivery, only dine-in or pickup. "
    "When the customer confirms pickup or dine-in and the cart is not empty, "
    "you MUST call generate_payment_link. "
    "Never create, guess, or invent a payment URL. "
    "Only send the payment URL returned by generate_payment_link. "
    "Do not say that you generated a payment link unless the tool was actually called."
    "Do not invent item prices"
    ),
    checkpointer=checkpointer,
)


def getmsg(human_msg, ph_num , name):
    start = time.time()
    config = {"configurable": {"thread_id": ph_num}}
    saved_state = agent.get_state(config).values
    response = agent.invoke(
        {
            "messages": [{"role": "user", "content": human_msg}],
            "cart": saved_state.get("cart", []),
            "phone_number": ph_num,
            "customer_name": name,
        },
        config,
    )
    print(f"agent.invoke took {time.time() - start:.2f}s")
    reply = response["messages"][-1].content
    print(f"DEBUG ai_reply: {repr(reply)}")
    if not reply:
        for m in reversed(response["messages"]):
            if getattr(m, "content", None):
                reply = m.content
                break
            else:
                reply = "Sorry, something went wrong on my end — could you try again?"
    return reply

import os
from dotenv import load_dotenv
from twilio.rest import Client
load_dotenv()
twilio_client = Client(
    os.environ["TWILIO_ACCOUNT_SID"],
    os.environ["TWILIO_AUTH_TOKEN"],
)
twilio_from = os.environ["TWILIO_WHATSAPP_FROM"]


def send_whatsapp(to: str, body: str) -> str:
    
    
    message = twilio_client.messages.create(
        body=body,
        from_=twilio_from,
        to=to,
    )
    return message.sid
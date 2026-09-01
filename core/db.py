
import os
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()

cached_menu=None

try:
    client = MongoClient(
        os.getenv("MONGODB_URI"),
        # serverSelectionTimeoutMS=int(os.getenv("MONGODB_SERVER_SELECTION_TIMEOUT_MS", "20000")),
        # connectTimeoutMS=int(os.getenv("MONGODB_CONNECT_TIMEOUT_MS", "20000")),
        # socketTimeoutMS=int(os.getenv("MONGODB_SOCKET_TIMEOUT_MS", "20000")),
    )
    db = client["DunaDakshin"]
    menu_collection = db["menu"]
    orders_collection = db["orders"]
except Exception as e:
    print(f"MongoDB connection setup failed: {e}")
    client = None
    menu_collection = None
    orders_collection = None



def extract_menu():
    global cached_menu
    if menu_collection is None:
        return "menu not loaded"
    try:
        cached_menu = list(menu_collection.find({}, {"_id": 0}))
        print(f"Loaded {len(cached_menu)} categories")
        return cached_menu
    except Exception as e:
        print(f"db call failed due to {e}")
        return {"error": str(e)}

extract_menu()


if __name__ == "__main__":
    try:
        client.admin.command("ping")
        print("MongoDB connection successful ")
    except Exception as e:
        print(f"MongoDB connection failed : {e}")



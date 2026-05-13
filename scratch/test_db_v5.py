import os
import ssl
import traceback
import certifi
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()

def test_db():
    uri = os.getenv("MONGO_URI")
    print(f"Testing URI: {uri[:20]}...")
    
    try:
        # Extremely loose SSL context
        context = ssl.create_default_context(cafile=certifi.where())
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE

        client = MongoClient(
            uri,
            serverSelectionTimeoutMS=5000,
            tlsContext=context
        )
        client.admin.command('ping')
        print("SUCCESS!")
    except Exception as e:
        print(f"FAILED: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    test_db()

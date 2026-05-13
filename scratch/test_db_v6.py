import os
import ssl
import traceback
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()

def test_db():
    uri = os.getenv("MONGO_URI")
    print(f"Testing URI: {uri[:20]}...")
    
    try:
        client = MongoClient(
            uri,
            serverSelectionTimeoutMS=5000,
            ssl=True,
            ssl_cert_reqs=ssl.CERT_NONE
        )
        client.admin.command('ping')
        print("SUCCESS!")
    except Exception as e:
        print(f"FAILED: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    test_db()

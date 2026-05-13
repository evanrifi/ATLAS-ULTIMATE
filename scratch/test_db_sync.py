import os
import traceback
from pymongo import MongoClient
import certifi
from dotenv import load_dotenv

load_dotenv()

def test_db():
    uri = os.getenv("MONGO_URI")
    print(f"Testing URI: {uri[:20]}...")
    
    try:
        client = MongoClient(
            uri,
            serverSelectionTimeoutMS=5000,
            tlsCAFile=certifi.where(),
            tlsAllowInvalidCertificates=True
        )
        client.admin.command('ping')
        print("✅ Sync MongoDB connection SUCCESSFUL!")
    except Exception as e:
        print("❌ Sync MongoDB connection FAILED")
        traceback.print_exc()

if __name__ == "__main__":
    test_db()

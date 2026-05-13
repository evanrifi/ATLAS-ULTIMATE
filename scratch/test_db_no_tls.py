import os
import traceback
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()

def test_db():
    uri = os.getenv("MONGO_URI")
    print(f"Testing URI: {uri[:20]}...")
    
    try:
        # Disabling TLS entirely (Atlas will likely reject this, but let's see the error)
        client = MongoClient(
            uri,
            serverSelectionTimeoutMS=5000,
            tls=False
        )
        client.admin.command('ping')
        print("Sync MongoDB connection SUCCESSFUL!")
    except Exception as e:
        print("Sync MongoDB connection FAILED")
        traceback.print_exc()

if __name__ == "__main__":
    test_db()

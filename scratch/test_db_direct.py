import os
import traceback
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()

def test_db():
    # Attempting to connect to a single shard directly to bypass SRV/DNS issues
    shard = "ac-2gaq13f-shard-00-00.qm7bfiu.mongodb.net:27017"
    user = "evan_wassim"
    pwd = "PASSWORD_REMOVED" # I'll get it from the .env
    
    uri = os.getenv("MONGO_URI")
    # Extract password from URI
    import re
    match = re.search(r'mongodb\+srv://([^:]+):([^@]+)@', uri)
    if not match:
        print("Could not parse URI")
        return
    
    user, pwd = match.groups()
    direct_uri = f"mongodb://{user}:{pwd}@{shard}/atlasunit?ssl=true&authSource=admin"
    
    print(f"Testing Direct URI: {direct_uri[:30]}...")
    
    try:
        client = MongoClient(
            direct_uri,
            serverSelectionTimeoutMS=5000,
            tlsAllowInvalidCertificates=True
        )
        client.admin.command('ping')
        print("✅ Direct MongoDB connection SUCCESSFUL!")
    except Exception as e:
        print("❌ Direct MongoDB connection FAILED")
        traceback.print_exc()

if __name__ == "__main__":
    test_db()

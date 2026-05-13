import asyncio
import os
import ssl
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

load_dotenv()

async def test_db():
    uri = os.getenv("MONGO_URI")
    print(f"Testing URI: {uri[:20]}...")
    
    # Create an insecure SSL context to bypass TLS version alerts
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    client = AsyncIOMotorClient(
        uri,
        serverSelectionTimeoutMS=5000,
        ssl_context=ctx
    )
    try:
        await client.admin.command('ping')
        print("MongoDB connection SUCCESSFUL!")
    except Exception as e:
        print(f"MongoDB connection FAILED: {str(e)[:200]}")

if __name__ == "__main__":
    asyncio.run(test_db())

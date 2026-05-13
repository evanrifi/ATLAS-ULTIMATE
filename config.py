import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    BOT_TOKEN = os.getenv("DISCORD_TOKEN")
    MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/atlas_python")
    
    # Construct Lavalink URI from HOST and PORT
    LAVALINK_HOST = os.getenv("LAVALINK_HOST", "lava.link")
    LAVALINK_PORT = os.getenv("LAVALINK_PORT", "80")
    LAVALINK_URI = f"http://{LAVALINK_HOST}:{LAVALINK_PORT}"
    
    LAVALINK_PASSWORD = os.getenv("LAVALINK_PASSWORD", "corz")
    VIRUSTOTAL_API_KEY = os.getenv("VT_API_KEY")
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    
    GUILD_ID = int(os.getenv("GUILD_ID")) if os.getenv("GUILD_ID") else None
    
    JTC_GAMING = int(os.getenv("JTC_GAMING", "0"))
    JTC_STUDY = int(os.getenv("JTC_STUDY", "0"))
    JTC_MUSIC = int(os.getenv("JTC_MUSIC", "0"))
    JTC_CHILL = int(os.getenv("JTC_CHILL", "0"))
    JOIN_TO_CREATE_ID = int(os.getenv("JOIN_TO_CREATE_ID", "0"))
    
    JTC_IDS = [JOIN_TO_CREATE_ID, JTC_GAMING, JTC_STUDY, JTC_MUSIC, JTC_CHILL]
    JTC_IDS = [i for i in JTC_IDS if i != 0]
    
    BANNER_GIF_URL = os.getenv("BANNER_GIF_URL")
    MOD_LOG_CHANNEL_ID = int(os.getenv("MOD_LOG_CHANNEL_ID", "0"))
    AUTO_ROLE_ID = int(os.getenv("AUTO_ROLE_ID", "0"))
    
    # Colors for embeds
    COLOR_PRIMARY = 0x2b2d31  # Discord dark theme color
    COLOR_SUCCESS = 0x57F287
    COLOR_ERROR = 0xED4245
    COLOR_INFO = 0x5865F2
    COLOR_WARNING = 0xFEE75C

"""
Generate a YouTube PO Token for Lavalink using yt-dlp.
Run: python gen_potoken.py
Then paste the output into application.yml under plugins.youtube
"""
import subprocess, json, sys

try:
    result = subprocess.run(
        ["python", "-m", "yt_dlp", "--cookies-from-browser", "chrome",
         "--print", "%(webpage_url)s", "--playlist-items", "1",
         "https://www.youtube.com/watch?v=dQw4w9WgXcQ"],
        capture_output=True, text=True, timeout=30
    )
    print("yt-dlp test output:", result.stdout[:200])
except Exception as e:
    print(f"Error: {e}")

#!/usr/bin/env python3
"""
Telegram authentication helper script
Run this on the server to authenticate Telethon session interactively
"""
import os
from telethon.sync import TelegramClient

# Get credentials from environment or hardcode for this one-time auth
API_ID = 38508832
API_HASH = "163fd4aef2ff289fb3b4fc1916695431"
PHONE = "+15512620848"
SESSION_FILE = "config/bossbot_session"

print("🔐 Telegram Authentication Helper")
print(f"Phone: {PHONE}")
print(f"Session will be saved to: {SESSION_FILE}")
print()

# Create config directory if it doesn't exist
os.makedirs("config", exist_ok=True)

# Create the client
client = TelegramClient(SESSION_FILE, API_ID, API_HASH)

print("Connecting to Telegram...")
client.start(phone=PHONE)

print()
print("✅ Authentication successful!")
print(f"Session saved to: {SESSION_FILE}.session")
print()
print("You can now run: docker-compose up -d app")

client.disconnect()

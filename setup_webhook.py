"""
Run this script ONCE after deploying to Vercel to register the webhook with Telegram.
Usage: python setup_webhook.py <your-vercel-url>
Example: python setup_webhook.py https://my-bot.vercel.app
"""
import sys
import os
import urllib.request
import json

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
if not TOKEN:
    print("Error: TELEGRAM_BOT_TOKEN not set.")
    sys.exit(1)

if len(sys.argv) < 2:
    print("Usage: python setup_webhook.py <your-vercel-url>")
    sys.exit(1)

vercel_url = sys.argv[1].rstrip("/")
webhook_url = f"{vercel_url}/api/webhook"

url = f"https://api.telegram.org/bot{TOKEN}/setWebhook"
data = json.dumps({"url": webhook_url, "allowed_updates": ["message", "callback_query"]}).encode()

req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
with urllib.request.urlopen(req) as resp:
    result = json.loads(resp.read())
    if result.get("ok"):
        print(f"Webhook set successfully: {webhook_url}")
    else:
        print(f"Failed: {result}")

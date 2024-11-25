import os
from flask import Flask, request
import requests

app = Flask(__name__)

# Webhook verification
@app.route('/webhook', methods=['GET'])
def verify():
    if request.args.get("hub.mode") == "subscribe" and request.args.get("hub.challenge"):
        if not request.args.get("hub.verify_token") == os.environ["VERIFY_TOKEN"]:
            return "Verification token mismatch", 403
        return request.args["hub.challenge"], 200
    return "Hello world", 200

# Handle incoming messages
@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.get_json()
    if data["object"] == "page":
        for entry in data["entry"]:
            for messaging_event in entry["messaging"]:
                sender_id = messaging_event["sender"]["id"]
                
                if messaging_event.get("message"):
                    if "text" in messaging_event["message"]:
                        messaging_text = messaging_event["message"]["text"]
                        # Echo the received message
                        send_message(sender_id, f"You sent: {messaging_text}")
    
    return "ok", 200

def send_message(recipient_id, message_text):
    params = {
        "access_token": os.environ["PAGE_ACCESS_TOKEN"]
    }
    headers = {
        "Content-Type": "application/json"
    }
    data = {
        "recipient": {
            "id": recipient_id
        },
        "message": {
            "text": message_text
        }
    }
    r = requests.post("https://graph.facebook.com/v2.6/me/messages", 
                     params=params, headers=headers, json=data)
    if r.status_code != 200:
        print(r.status_code)
        print(r.text)

# Debug route
@app.route('/debug', methods=['GET'])
def debug():
    return {
        "VERIFY_TOKEN": os.environ.get("VERIFY_TOKEN", "Token not set"),
        "PAGE_ACCESS_TOKEN": "Hidden for security"
    }

# Basic test route
@app.route('/', methods=['GET'])
def index():
    return 'Hello World!'

if __name__ == '__main__':
    app.run(port=int(os.environ.get("PORT", 8000)))

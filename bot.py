from flask import Flask, request
import requests
import os
import json

app = Flask(__name__)

@app.route('/', methods=['GET'])
def verify():
    return "Bot is running!"

@app.route('/webhook', methods=['GET'])
def verify_webhook():
    if request.args.get("hub.mode") == "subscribe" and request.args.get("hub.challenge"):
        if not request.args.get("hub.verify_token") == os.environ["VERIFY_TOKEN"]:
            return "Token verification failed", 403
        return request.args["hub.challenge"], 200
    return "Hello", 200

@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.get_json()
    if data["object"] == "page":
        for entry in data["entry"]:
            for messaging_event in entry["messaging"]:
                sender_id = messaging_event["sender"]["id"]
                
                if messaging_event.get("message"):
                    if "text" in messaging_event["message"]:
                        received_text = messaging_event["message"]["text"].lower()
                        
                        # Simple response test
                        if received_text in ["hi", "hello", "привіт"]:
                            send_message(sender_id, "Привіт! 👋 Я допоможу вам замовити яйця!")
    return "ok", 200

def send_message(recipient_id, message_text):
    data = {
        "recipient": {"id": recipient_id},
        "message": {"text": message_text}
    }
    
    params = {
        "access_token": os.environ["PAGE_ACCESS_TOKEN"]
    }
    headers = {
        "Content-Type": "application/json"
    }
    
    r = requests.post(
        "https://graph.facebook.com/v2.6/me/messages",
        params=params,
        headers=headers,
        json=data
    )
    
    if r.status_code != 200:
        print(r.status_code)
        print(r.text)

if __name__ == "__main__":
    app.run(debug=True)

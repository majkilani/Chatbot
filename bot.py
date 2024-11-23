from flask import Flask, request
import requests
import json
import os

app = Flask(__name__)

# Your tokens here
PAGE_ACCESS_TOKEN =
"EAAXuqkbSalgBO37zP9ofVIVmmSljOPI34JVevXUJWLU48HZA1ZAO36EsuZBXINA0rZCRwcy8mqvLEZBP99D776SkDsJW3m5zLTqQ9ZB2YvVrcUtUkIzEcnBJdEIQPxyY6xXbLj2ITrZCP1ruxIV5NbXTuEJJHZC98X7mgy4rFDT6D7289F688YO77bEAWfQZBCDhqEMNEUlaFOyCGRgIZD"
VERIFY_TOKEN = "my-secret-token"
PERPLEXITY_API_KEY = "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"

def get_perplexity_response(message):
    url = "https://api.perplexity.ai/chat/completions"
    headers = {
        "Authorization": f"Bearer {PERPLEXITY_API_KEY}",
        "Content-Type": "application/json"
    }
    
    data = {
        "model": "mixtral-8x7b-instruct",  # or another model you prefer
        "messages": [
            {
                "role": "system",
                "content": "You are a helpful assistant. Respond in a friendly and concise manner."
            },
            {
                "role": "user",
                "content": message
            }
        ]
    }
    
    try:
        response = requests.post(url, headers=headers, json=data)
        if response.status_code == 200:
            return response.json()['choices'][0]['message']['content']
        else:
            return f"Error: {response.status_code}"
    except Exception as e:
        return f"Error: {str(e)}"

def send_message(recipient_id, message_text):
    params = {
        "access_token": PAGE_ACCESS_TOKEN
    }
    headers = {
        "Content-Type": "application/json"
    }
    data = json.dumps({
        "recipient": {
            "id": recipient_id
        },
        "message": {
            "text": message_text
        }
    })
    
    r = requests.post(
        "https://graph.facebook.com/v13.0/me/messages",
        params=params,
        headers=headers,
        data=data
    )
    return r.json()

@app.route('/', methods=['GET'])
def verify():
    if request.args.get("hub.mode") == "subscribe" and request.args.get("hub.challenge"):
        if request.args.get("hub.verify_token") == VERIFY_TOKEN:
            return request.args["hub.challenge"]
        return "Verification token mismatch", 403
    return "Hello world", 200

@app.route('/', methods=['POST'])
def webhook():
    data = request.get_json()
    
    if data["object"] == "page":
        for entry in data["entry"]:
            for messaging_event in entry["messaging"]:
                if messaging_event.get("message"):
                    sender_id = messaging_event["sender"]["id"]
                    message_text = messaging_event["message"]["text"]
                    
                    # Get response from Perplexity API
                    ai_response = get_perplexity_response(message_text)
                    
                    # Send response back to user
                    send_message(sender_id, ai_response)
    
    return "ok", 200

if __name__ == '__main__':
    app.run(debug=True)

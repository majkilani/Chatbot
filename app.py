import os
from flask import Flask, request
import requests
from dotenv import load_dotenv
import json

load_dotenv()

app = Flask(__name__)

VERIFY_TOKEN = os.environ.get('VERIFY_TOKEN')
PAGE_ACCESS_TOKEN = os.environ.get('PAGE_ACCESS_TOKEN')
PERPLEXITY_API_KEY = os.environ.get('PERPLEXITY_API_KEY')

def get_perplexity_response(user_message):
    """Get response from Perplexity AI API"""
    headers = {
        "Authorization": f"Bearer {PERPLEXITY_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": "llama-3.1-sonar-small-128k-online",
        "messages": [
            {
                "role": "system",
                "content": "Be precise and concise."
            },
            {
                "role": "user",
                "content": user_message
            }
        ],
        "temperature": 0.2,
        "top_p": 0.9,
        "return_images": False,
        "return_related_questions": False
    }

    try:
        response = requests.post(
            "https://api.perplexity.ai/chat/completions",
            headers=headers,
            json=payload
        )
        
        if response.status_code == 200:
            response_data = response.json()
            return response_data['choices'][0]['message']['content']
        else:
            print(f"API Error: {response.status_code}")
            print(f"Response: {response.text}")
            return f"Sorry, I couldn't process your request at this time. Status code: {response.status_code}"

    except Exception as e:
        print(f"Error: {str(e)}")
        return "Sorry, an error occurred while processing your request."

def send_message(recipient_id, message_text):
    """Send message to user through Facebook Messenger"""
    params = {
        "access_token": PAGE_ACCESS_TOKEN
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

    try:
        response = requests.post(
            "https://graph.facebook.com/v2.6/me/messages",
            params=params,
            headers=headers,
            json=data
        )
        if response.status_code != 200:
            print(f"Failed to send message: {response.status_code}")
            print(f"Response: {response.text}")
    except Exception as e:
        print(f"Error sending message: {str(e)}")

@app.route('/', methods=['GET'])
def verify():
    if request.args.get("hub.mode") == "subscribe" and request.args.get("hub.challenge"):
        if request.args.get("hub.verify_token") == VERIFY_TOKEN:
            return request.args.get("hub.challenge")
        return "Invalid verification token"
    return "Hello world"

@app.route('/', methods=['POST'])
def webhook():
    data = request.get_json()
    
    if data["object"] == "page":
        for entry in data["entry"]:
            for messaging_event in entry["messaging"]:
                if messaging_event.get("message"):
                    sender_id = messaging_event["sender"]["id"]
                    if "text" in messaging_event["message"]:
                        message_text = messaging_event["message"]["text"]
                        
                        # Get response from Perplexity
                        ai_response = get_perplexity_response(message_text)
                        
                        # Send response back to user
                        send_message(sender_id, ai_response)

    return "ok", 200

if __name__ == "__main__":
    app.run(debug=True)

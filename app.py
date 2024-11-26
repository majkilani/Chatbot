import os
import json
import requests
from flask import Flask, request

app = Flask(__name__)

# Environment Variables - Adding DUMPLING_API_KEY
PAGE_ACCESS_TOKEN = os.environ.get('PAGE_ACCESS_TOKEN')
VERIFY_TOKEN = os.environ.get('VERIFY_TOKEN')
PERPLEXITY_API_KEY = os.environ.get('PERPLEXITY_API_KEY')
DUMPLING_API_KEY = os.environ.get('DUMPLING_API_KEY')  # New addition

def get_perplexity_response(user_message):
    """Get response from Perplexity API"""
    headers = {
        "Authorization": f"Bearer {PERPLEXITY_API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": "mixtral-8x7b-instruct",
        "messages": [{"role": "user", "content": user_message}]
    }
    
    response = requests.post(
        "https://api.perplexity.ai/chat/completions",
        headers=headers,
        json=payload
    )
    
    if response.status_code == 200:
        return response.json()['choices'][0]['message']['content']
    else:
        raise Exception(f"Perplexity API Error: {response.status_code}")

def get_dumpling_response(user_message):
    """Get response from Dumpling AI API"""
    headers = {
        "Authorization": f"Bearer {DUMPLING_API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "message": user_message,
        "stream": False
    }
    
    response = requests.post(
        "https://api.dumplingai.com/api/v1/chatbot/generate",
        headers=headers,
        json=payload
    )
    
    if response.status_code == 200:
        return response.json()['response']
    else:
        raise Exception(f"Dumpling API Error: {response.status_code}")

@app.route('/', methods=['GET'])
def verify():
    if request.args.get("hub.mode") == "subscribe" and request.args.get("hub.challenge"):
        if not request.args.get("hub.verify_token") == VERIFY_TOKEN:
            return "Verification token mismatch", 403
        return request.args["hub.challenge"], 200
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
                    
                    try:
                        # Try Perplexity first, if it fails, use Dumpling as backup
                        try:
                            response_text = get_perplexity_response(message_text)
                        except Exception as perplexity_error:
                            print(f"Perplexity API error: {perplexity_error}")
                            response_text = get_dumpling_response(message_text)
                        
                        send_message(sender_id, response_text)
                    except Exception as e:
                        error_message = "Sorry, I encountered an error processing your request."
                        send_message(sender_id, error_message)
                        print(f"Error: {str(e)}")
    return "ok", 200

def send_message(recipient_id, message_text):
    """Send message to Facebook user"""
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
    response = requests.post(
        "https://graph.facebook.com/v2.6/me/messages",
        params=params,
        headers=headers,
        json=data
    )
    if response.status_code != 200:
        print(response.status_code)
        print(response.text)

if __name__ == '__main__':
    app.run(debug=True, port=5000)

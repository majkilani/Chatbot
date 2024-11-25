import os
from flask import Flask, request
import requests
from dotenv import load_dotenv
import json
import logging

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

load_dotenv()

app = Flask(__name__)

VERIFY_TOKEN = os.environ.get('VERIFY_TOKEN')
PAGE_ACCESS_TOKEN = os.environ.get('PAGE_ACCESS_TOKEN')
PERPLEXITY_API_KEY = os.environ.get('PERPLEXITY_API_KEY')

def verify_page_token():
    try:
        response = requests.get(
            f"https://graph.facebook.com/debug_token",
            params={
                "input_token": PAGE_ACCESS_TOKEN,
                "access_token": PAGE_ACCESS_TOKEN
            }
        )
        logger.debug(f"Token verification response: {response.json()}")
        return response.status_code == 200
    except Exception as e:
        logger.error(f"Token verification error: {str(e)}")
        return False

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
        logger.debug(f"Sending request to Perplexity API: {payload}")
        response = requests.post(
            "https://api.perplexity.ai/chat/completions",
            headers=headers,
            json=payload
        )
        
        logger.debug(f"Perplexity API response status: {response.status_code}")
        logger.debug(f"Perplexity API response: {response.text}")
        
        if response.status_code == 200:
            response_data = response.json()
            return response_data['choices'][0]['message']['content']
        else:
            logger.error(f"API Error: {response.status_code}")
            logger.error(f"Response: {response.text}")
            return f"Sorry, I couldn't process your request at this time. Status code: {response.status_code}"

    except Exception as e:
        logger.error(f"Error: {str(e)}")
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
            "text": message_text[:2000]  # Facebook has a 2000 character limit
        }
    }

    logger.debug(f"Sending message to {recipient_id}: {message_text[:100]}...")

    try:
        response = requests.post(
            "https://graph.facebook.com/v18.0/me/messages",
            params=params,
            headers=headers,
            json=data
        )
        logger.debug(f"Facebook API response status: {response.status_code}")
        logger.debug(f"Facebook API response: {response.text}")
        
        if response.status_code != 200:
            logger.error(f"Failed to send message: {response.status_code}")
            logger.error(f"Response: {response.text}")
            return False
        return True
            
    except Exception as e:
        logger.error(f"Error sending message: {str(e)}")
        return False

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
    logger.debug(f"Received webhook data: {data}")
    
    if data["object"] == "page":
        for entry in data["entry"]:
            for messaging_event in entry["messaging"]:
                if messaging_event.get("message"):
                    sender_id = messaging_event["sender"]["id"]
                    logger.debug(f"Sender ID: {sender_id}")
                    
                    if "text" in messaging_event["message"]:
                        message_text = messaging_event["message"]["text"]
                        logger.debug(f"Received message: {message_text}")
                        
                        # Get response from Perplexity
                        ai_response = get_perplexity_response(message_text)
                        logger.debug(f"Perplexity response: {ai_response}")
                        
                        # Send response back to user
                        if send_message(sender_id, ai_response):
                            logger.debug("Message sent successfully")
                        else:
                            logger.error("Failed to send message")

    return "ok", 200

if __name__ == "__main__":
    if verify_page_token():
        logger.info("Page token is valid")
    else:
        logger.error("Page token is invalid")
    app.run(debug=True)

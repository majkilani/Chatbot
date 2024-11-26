import os
import logging
import requests
from flask import Flask, request
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Environment variables
PAGE_ACCESS_TOKEN = os.environ.get('PAGE_ACCESS_TOKEN')
VERIFY_TOKEN = os.environ.get('VERIFY_TOKEN')
DUMPLING_API_KEY = os.environ.get('DUMPLING_API_KEY')

def get_dumpling_response(user_message: str) -> str:
    """Get response from Dumpling AI API"""
    try:
        headers = {
            "Authorization": f"Bearer {DUMPLING_API_KEY}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "messages": [
                {
                    "role": "user",
                    "content": user_message
                }
            ]
        }
        
        response = requests.post(
            "https://api.dumpling.ai/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=10
        )
        
        logger.info(f"Dumpling API Response Status: {response.status_code}")
        
        if response.status_code == 200:
            return response.json()['choices'][0]['message']['content']
        else:
            logger.error(f"Dumpling API Error: {response.status_code} - {response.text}")
            return "Вибачте, виникла технічна помилка. Будь ласка, зателефонуйте нам за номером 0953314400."
            
    except Exception as e:
        logger.error(f"Error in get_dumpling_response: {str(e)}")
        return "Вибачте, виникла технічна помилка. Будь ласка, зателефонуйте нам за номером 0953314400."

def send_message(recipient_id: str, message_text: str):
    """Send message to user through Facebook Messenger"""
    try:
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
            "https://graph.facebook.com/v18.0/me/messages",
            params=params,
            headers=headers,
            json=data
        )
        
        if response.status_code != 200:
            logger.error(f"Failed to send message: {response.status_code} - {response.text}")
            
    except Exception as e:
        logger.error(f"Error sending message: {str(e)}")

@app.route("/webhook", methods=['POST'])
def webhook():
    """Handle incoming messages from Facebook"""
    data = request.get_json()
    logger.debug(f"Received webhook data: {data}")

    if data["object"] == "page":
        for entry in data["entry"]:
            if "messaging" in entry:
                for messaging_event in entry["messaging"]:
                    sender_id = messaging_event["sender"]["id"]
                    
                    if "message" in messaging_event and "text" in messaging_event["message"]:
                        message_text = messaging_event["message"]["text"]
                        logger.info(f"Received message: {message_text}")
                        
                        logger.info("Attempting to get Dumpling AI response")
                        ai_response = get_dumpling_response(message_text)
                        
                        if ai_response:
                            logger.info(f"Sending response: {ai_response}")
                            send_message(sender_id, ai_response)
                        else:
                            error_message = "Вибачте, виникла помилка. Будь ласка, зателефонуйте нам за номером 0953314400."
                            send_message(sender_id, error_message)
                            
    return "OK", 200

@app.route("/test", methods=['GET'])
def test_api():
    """Test endpoint to verify API connections"""
    try:
        # Test Dumpling AI API
        test_response = get_dumpling_response("Test message")
        dumpling_status = "OK" if test_response else "Failed"

        return {
            "dumpling_api": dumpling_status,
            "environment_variables": {
                "PAGE_ACCESS_TOKEN": "Set" if PAGE_ACCESS_TOKEN else "Missing",
                "VERIFY_TOKEN": "Set" if VERIFY_TOKEN else "Missing",
                "DUMPLING_API_KEY": "Set" if DUMPLING_API_KEY else "Missing"
            }
        }
    except Exception as e:
        return {"error": str(e)}

if __name__ == "__main__":
    app.run(debug=True)

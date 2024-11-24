import os
import sys
from flask import Flask, request
import requests
import logging

app = Flask(__name__)

# Set up logging
logging.basicConfig(level=logging.DEBUG)

# Environment variables with error handling
VERIFY_TOKEN = os.environ.get('myspecialtoken123')
if not VERIFY_TOKEN:
    app.logger.error("VERIFY_TOKEN not set in environment variables")
    
PAGE_ACCESS_TOKEN = os.environ.get('EAAXuqkbSalgBO37zP9ofVIVmmSljOPI34JVevXUJWLU48HZA1ZAO36EsuZBXINA0rZCRwcy8mqvLEZBP99D776SkDsJW3m5zLTqQ9ZB2YvVrcUtUkIzEcnBJdEIQPxyY6xXbLj2ITrZCP1ruxIV5NbXTuEJJHZC98X7mgy4rFDT6D7289F688YO77bEAWfQZBCDhqEMNEUlaFOyCGRgIZD')
if not PAGE_ACCESS_TOKEN:
    app.logger.error("PAGE_ACCESS_TOKEN not set in environment variables")

PERPLEXITY_API_KEY = os.environ.get('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')
if not PERPLEXITY_API_KEY:
    app.logger.error("PERPLEXITY_API_KEY not set in environment variables")

@app.route('/')
def home():
    return 'Hello! This is your Facebook Messenger Bot'

@app.route('/webhook', methods=['GET'])
def verify():
    try:
        app.logger.info("Received verification request")
        hub_verify_token = request.args.get('hub.verify_token')
        hub_challenge = request.args.get('hub.challenge')
        
        app.logger.info(f"Verify Token Received: {hub_verify_token}")
        app.logger.info(f"Expected Token: {VERIFY_TOKEN}")
        
        if hub_verify_token == VERIFY_TOKEN:
            app.logger.info("Verification successful")
            return hub_challenge
        else:
            app.logger.warning("Verification failed - token mismatch")
            return 'Invalid verification token'
            
    except Exception as e:
        app.logger.error(f"Error in verify endpoint: {str(e)}")
        return str(e), 500

@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        data = request.get_json()
        app.logger.info(f"Received webhook data: {data}")
        
        if data['object'] == 'page':
            for entry in data['entry']:
                for messaging_event in entry['messaging']:
                    if messaging_event.get('message'):
                        sender_id = messaging_event['sender']['id']
                        message_text = messaging_event['message'].get('text')
                        
                        if message_text:
                            send_message(sender_id, f"You said: {message_text}")
        return 'ok'
        
    except Exception as e:
        app.logger.error(f"Error in webhook endpoint: {str(e)}")
        return str(e), 500

def send_message(recipient_id, message_text):
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
        r = requests.post("https://graph.facebook.com/v2.6/me/messages", 
                         params=params, headers=headers, json=data)
        
        if r.status_code != 200:
            app.logger.error(f"Failed to send message. Status: {r.status_code}")
            app.logger.error(f"Response: {r.text}")
            
    except Exception as e:
        app.logger.error(f"Error in send_message: {str(e)}")

@app.errorhandler(500)
def internal_error(error):
    app.logger.error(f"500 error: {error}")
    return "Internal Server Error", 500

@app.errorhandler(Exception)
def handle_exception(e):
    app.logger.error(f"Unhandled exception: {str(e)}")
    return str(e), 500

if __name__ == '__main__':
    app.run(debug=True)

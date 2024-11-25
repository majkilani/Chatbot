import os
import sys
from flask import Flask, request
import requests
import logging

app = Flask(__name__)

# Set up logging
logging.basicConfig(level=logging.DEBUG)

# Environment variables with error handling
VERIFY_TOKEN = os.environ.get('VERIFY_TOKEN')  # Don't put the actual token here
if not VERIFY_TOKEN:
    app.logger.error("VERIFY_TOKEN not set in environment variables")
    
PAGE_ACCESS_TOKEN = os.environ.get('PAGE_ACCESS_TOKEN')  # Don't put the actual token here
if not PAGE_ACCESS_TOKEN:
    app.logger.error("PAGE_ACCESS_TOKEN not set in environment variables")

PERPLEXITY_API_KEY = os.environ.get('PERPLEXITY_API_KEY')  # Don't put the actual key here
if not PERPLEXITY_API_KEY:
    app.logger.error("PERPLEXITY_API_KEY not set in environment variables")

@app.route('/')
def home():
    return 'Bot is running!'

@app.route('/webhook', methods=['GET'])
def verify():
    app.logger.info(f"All request args: {request.args}")
    
    verify_token = request.args.get('hub.verify_token')
    challenge = request.args.get('hub.challenge')
    
    app.logger.info(f"Received verify_token: {verify_token}")
    app.logger.info(f"Expected VERIFY_TOKEN: {VERIFY_TOKEN}")
    app.logger.info(f"Challenge: {challenge}")

    if verify_token == VERIFY_TOKEN:
        app.logger.info("Token verified successfully!")
        if challenge is not None:
            return challenge
        return "Token verified but no challenge received"
    
    return f'Invalid verify token'

@app.route('/webhook', methods=['POST'])
def webhook():
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

def send_message(recipient_id, message_text):
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
        app.logger.error(f"Failed to send message: Status {r.status_code}")
        app.logger.error(f"Response: {r.text}")

if __name__ == '__main__':
    app.run(debug=True)

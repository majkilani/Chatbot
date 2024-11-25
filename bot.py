import os
from flask import Flask, request
import requests
from dotenv import load_dotenv
import json

# Load environment variables
load_dotenv()

app = Flask(__name__)

# Environment variables
VERIFY_TOKEN = os.environ.get('VERIFY_TOKEN')
PAGE_ACCESS_TOKEN = os.environ.get('PAGE_ACCESS_TOKEN')
PERPLEXITY_API_KEY = os.environ.get('PERPLEXITY_API_KEY')

def get_perplexity_response(prompt):
    """Get response from Perplexity AI API"""
    headers = {
        "Authorization": f"Bearer {PERPLEXITY_API_KEY}",
        "Content-Type": "application/json"
    }
    
    data = {
        "model": "mistral-7b-instruct",
        "messages": [{"role": "user", "content": prompt}]
    }
    
    try:
        response = requests.post(
            "https://api.perplexity.ai/chat/completions",
            headers=headers,
            json=data
        )
        
        if response.status_code == 200:
            return response.json()['choices'][0]['message']['content']
        else:
            print(f"Error from Perplexity API: {response.status_code} - {response.text}")
            return "Sorry, I couldn't process your request at this time."
    except Exception as e:
        print(f"Exception while calling Perplexity API: {str(e)}")
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
            print(f"Error sending message: {response.status_code} - {response.text}")
            
        return response.json()
    except Exception as e:
        print(f"Exception while sending message: {str(e)}")
        return None

@app.route('/webhook', methods=['GET'])
def verify():
    """Handle the initial verification of the webhook"""
    if request.args.get('hub.verify_token') == VERIFY_TOKEN:
        return request.args.get('hub.challenge')
    return 'Invalid verification token'

@app.route('/webhook', methods=['POST'])
def webhook():
    """Handle incoming messages"""
    data = request.get_json()
    
    if data['object'] == 'page':
        for entry in data['entry']:
            for messaging_event in entry['messaging']:
                if messaging_event.get('message'):
                    try:
                        # Get the sender ID and message text
                        sender_id = messaging_event['sender']['id']
                        message_text = messaging_event['message'].get('text', '')
                        
                        if message_text:
                            # Get response from Perplexity
                            response_text = get_perplexity_response(message_text)
                            
                            # Split long responses if necessary (Messenger has a 2000 character limit)
                            if len(response_text) > 1900:  # Leave some margin
                                chunks = [response_text[i:i+1900] for i in range(0, len(response_text), 1900)]
                                for chunk in chunks:
                                    send_message(sender_id, chunk)
                            else:
                                send_message(sender_id, response_text)
                        else:
                            send_message(sender_id, "I can only process text messages.")
                            
                    except Exception as e:
                        print(f"Error processing message: {str(e)}")
                        send_message(sender_id, "Sorry, something went wrong while processing your message.")
                        
    return 'ok'

@app.route('/privacy', methods=['GET'])
def privacy():
    """Privacy policy endpoint"""
    return 'Privacy Policy: This bot stores no personal information.'

@app.route('/terms', methods=['GET'])
def terms():
    """Terms of service endpoint"""
    return 'Terms of Service: Use at your own risk.'

if __name__ == '__main__':
    app.run(debug=True)

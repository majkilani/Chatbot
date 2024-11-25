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
    print(f"Sending request to Perplexity API with prompt: {prompt}")
    print(f"Using API key: {PERPLEXITY_API_KEY[:5]}...") # Print first 5 chars of API key for verification
    
    headers = {
        "Authorization": f"Bearer {PERPLEXITY_API_KEY}",
        "Content-Type": "application/json"
    }
    
    data = {
        "model": "mistral-7b-instruct",
        "messages": [{"role": "user", "content": prompt}]
    }
    
    try:
        print("Making request to Perplexity API...")
        response = requests.post(
            "https://api.perplexity.ai/chat/completions",
            headers=headers,
            json=data
        )
        
        print(f"Perplexity API Response Status Code: {response.status_code}")
        print(f"Perplexity API Response: {response.text}")
        
        if response.status_code == 200:
            result = response.json()['choices'][0]['message']['content']
            print(f"Successfully got response: {result[:100]}...")  # Print first 100 chars
            return result
        else:
            print(f"Error from Perplexity API: {response.status_code} - {response.text}")
            return f"Sorry, I couldn't process your request at this time. Status code: {response.status_code}"
    except Exception as e:
        print(f"Exception while calling Perplexity API: {str(e)}")
        return f"Sorry, an error occurred while processing your request. Error: {str(e)}"

def send_message(recipient_id, message_text):
    """Send message to user through Facebook Messenger"""
    print(f"Sending message to {recipient_id}: {message_text[:100]}...")  # Print first 100 chars
    
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
        
        print(f"Facebook API Response Status Code: {response.status_code}")
        print(f"Facebook API Response: {response.text}")
        
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
    print(f"Received webhook data: {json.dumps(data, indent=2)}")
    
    if data['object'] == 'page':
        for entry in data['entry']:
            for messaging_event in entry['messaging']:
                if messaging_event.get('message'):
                    try:
                        # Get the sender ID and message text
                        sender_id = messaging_event['sender']['id']
                        message_text = messaging_event['message'].get('text', '')
                        
                        print(f"Received message from {sender_id}: {message_text}")
                        
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
                        send_message(sender_id, f"Sorry, something went wrong while processing your message. Error: {str(e)}")
                        
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

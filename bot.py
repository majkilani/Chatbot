import os
import json
import logging
from flask import Flask, request, jsonify
import requests
import httpx

app = Flask(__name__)

# Enhanced debugging
@app.route('/debug')
def debug_vars():
    return {
        'VERIFY_TOKEN': os.environ.get('VERIFY_TOKEN', 'Not Set'),
        'PAGE_ACCESS_TOKEN': os.environ.get('PAGE_ACCESS_TOKEN', 'Not Set')[:10] + '...',  # Show first 10 chars only
        'PERPLEXITY_API_KEY': os.environ.get('PERPLEXITY_API_KEY', 'Not Set')[:10] + '...'  # Show first 10 chars only
    }

@app.route('/')
def hello():
    return 'Bot is running!'

@app.route('/webhook', methods=['GET'])
def verify():
    app.logger.info("Webhook GET request received")
    app.logger.info(f"Request args: {request.args}")
    
    verify_token = request.args.get('hub.verify_token')
    challenge = request.args.get('hub.challenge')
    
    app.logger.info(f"Received verify_token: {verify_token}")
    app.logger.info(f"Expected VERIFY_TOKEN: {os.environ.get('VERIFY_TOKEN')}")
    app.logger.info(f"Challenge: {challenge}")

    if verify_token == os.environ.get('VERIFY_TOKEN'):
        app.logger.info("Token verified successfully!")
        return challenge
    else:
        app.logger.error(f"Token verification failed. Received: {verify_token}, Expected: {os.environ.get('VERIFY_TOKEN')}")
        return 'Invalid verify token'

@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.get_json()
    app.logger.info(f"Received webhook data: {data}")  # Log the incoming webhook data

    if data['object'] == 'page':
        for entry in data['entry']:
            for messaging_event in entry['messaging']:
                sender_id = messaging_event['sender']['id']
                
                if 'message' in messaging_event and 'text' in messaging_event['message']:
                    message_text = messaging_event['message']['text']
                    app.logger.info(f"Received message: {message_text} from sender: {sender_id}")
                    
                    try:
                        # Get response from Perplexity API
                        response_text = get_perplexity_response(message_text)
                        app.logger.info(f"Perplexity API response: {response_text}")
                        
                        # Send message back
                        send_message(sender_id, response_text)
                        app.logger.info(f"Message sent successfully to {sender_id}")
                    except Exception as e:
                        app.logger.error(f"Error processing message: {str(e)}")
                        send_message(sender_id, "Sorry, I encountered an error processing your message.")

        return 'OK', 200
    return 'Invalid request', 404

def get_perplexity_response(message):
    url = "https://api.perplexity.ai/chat/completions"
    
    headers = {
        "Authorization": f"Bearer {os.environ.get('PERPLEXITY_API_KEY')}",
        "Content-Type": "application/json"
    }
    
    data = {
        "model": "mixtral-8x7b-instruct",
        "messages": [
            {
                "role": "user",
                "content": message
            }
        ]
    }

    app.logger.info(f"Sending request to Perplexity API: {data}")
    
    try:
        response = requests.post(url, headers=headers, json=data)
        response.raise_for_status()  # Raise an exception for bad status codes
        response_data = response.json()
        app.logger.info(f"Perplexity API raw response: {response_data}")
        
        return response_data['choices'][0]['message']['content']
    except Exception as e:
        app.logger.error(f"Error calling Perplexity API: {str(e)}")
        raise

def send_message(recipient_id, message_text):
    url = f"https://graph.facebook.com/v2.6/me/messages?access_token={os.environ.get('PAGE_ACCESS_TOKEN')}"
    
    data = {
        "recipient": {"id": recipient_id},
        "message": {"text": message_text}
    }
    
    try:
        response = requests.post(url, json=data)
        response.raise_for_status()  # Raise an exception for bad status codes
        app.logger.info(f"Message sent successfully: {response.json()}")
    except Exception as e:
        app.logger.error(f"Error sending message: {str(e)}")
        raise

if __name__ == '__main__':
    # Set up logging
    logging.basicConfig(level=logging.INFO)
    app.run(debug=True, port=os.getenv('PORT', 5000))

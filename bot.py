import os
from flask import Flask, request
import requests

app = Flask(__name__)

# Environment variables
VERIFY_TOKEN = os.environ.get('y-secret-token')
PAGE_ACCESS_TOKEN = os.environ.get('EAAXuqkbSalgBO37zP9ofVIVmmSljOPI34JVevXUJWLU48HZA1ZAO36EsuZBXINA0rZCRwcy8mqvLEZBP99D776SkDsJW3m5zLTqQ9ZB2YvVrcUtUkIzEcnBJdEIQPxyY6xXbLj2ITrZCP1ruxIV5NbXTuEJJHZC98X7mgy4rFDT6D7289F688YO77bEAWfQZBCDhqEMNEUlaFOyCGRgIZD')
PERPLEXITY_API_KEY = os.environ.get('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')

@app.route('/', methods=['GET'])
def verify():
    if request.args.get('hub.verify_token') == VERIFY_TOKEN:
        return request.args.get('hub.challenge')
    return 'Invalid verification token'

@app.route('/', methods=['POST'])
def webhook():
    data = request.get_json()
    if data['object'] == 'page':
        for entry in data['entry']:
            for messaging_event in entry['messaging']:
                if messaging_event.get('message'):
                    sender_id = messaging_event['sender']['id']
                    message_text = messaging_event['message'].get('text')
                    
                    if message_text:
                        # Send the response back to Facebook
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
        print(r.status_code)
        print(r.text)

if __name__ == '__main__':
    app.run()

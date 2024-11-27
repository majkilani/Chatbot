from flask import Flask, request, session, jsonify
from flask_restful import Resource, Api, abort, reqparse
from functools import lru_cache
import requests
import os
import logging
from dotenv import load_dotenv
import random

API_NAME = 'EggsCom'
load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', os.urandom(24))
api = Api(app)

PERPLEXITY_API_KEY = os.environ.get('PERPLEXITY_API_KEY', 'default-key-if-not-set')
PERPLEXITY_ENDPOINT = os.environ.get('PERPLEXITY_ENDPOINT', 'https://api.perplexity.ai/chat/completions')
 
# Logging setup
log_format = logging.Formatter('[%(asctime)s] %(levelname)s|%(method)s (%(host)s) %(message)s')
log_handler = logging.StreamHandler()
log_handler.setFormatter(log_format)
app.logger.handlers = log_handler
app.logger.addHandler(log_handler)
app.logger.setLevel(logging.INFO)

# Cache for non-api messages
non_api_messages = {
    'hello': "Доброго дня! Як я можу допомогти вам з вашими яйцями сьогодні?",
    'good work': "Дякую, я стараюсь бути найдопомоговим ботом для вас! ✨ Вас зацікавили яйця? Ось кілька опцілей для вас:",
    'goodbye': "Бувайте! Зв'яжіться з нами знову, якщо у вас будуть будь-які запитання..."
}

class UserConversation:
    def __init__(self):
        self.context = None
        self.last_message = None
        self.ordering_data = {}

user_conversations = {}

def generate_otp():
    return format(random.randint(100000, 999999), '06d')

def send_otp(phone, otp):
    # Implement SMS functionality or log the OTP
    app.logger.info(f'Send OTP {otp} to {phone}')

@lru_cache(maxsize=200)
def get_cached_menu():
    return 'Наше меню включає ...' # Placeholder

@lru_cache(maxsize=100)
def perplexity(message):
    if not PERPLEXITY_API_KEY:
        app.logger.warning("Perplexity API key not set.")
        return "Sorry, the AI service is currently unavailable."
    
    data = {"message": message}
    headers = {"Authorization": f"Bearer {PERPLEXITY_API_KEY}"}
    
    try:
        response = requests.post(PERPLEXITY_ENDPOINT, headers=headers, json=data)
        response.raise_for_status()
        response_json = response.json()
        return response_json.get('completions', [{}]).get('text')
    except requests.exceptions.RequestException as e:
        app.logger.error(f"An error occurred when accessing the Perplexity API: {e}")
        return "Sorry, there was an error processing your request."

def prompt_user(state):
    if state.context == 'order_in_progress':
        if 'amount' not in state.ordering_data:
            return 'Скільки яєць ви бажаєте замовити? Будь ласка, введіть кількість.'
        elif not state.ordering_data.get('address'):
            return 'Будь ласка, введіть вашу адресу доставки.'
        else:
            return 'Ваше замовлення оформлене. Дякуємо!'

def authenticate_change(sender_id):
    if sender_id not in session:
        session[sender_id] = UserConversation(phone=None)
    session[sender_id].otp = generate_otp()
    phone = user_conversations.get(sender_id, {}).get('phone')
    if phone:
        send_otp(phone, session[sender_id].otp)
    else:
        app.logger.error(f'Trying to send OTP without user phone number for sender ID: {sender_id}')
    return "Ми відправили OTP на ваш номер телефону. Будь ласка, введіть його тут:"

@app.route('/webhook', methods=['POST'])
def callback_handler():
    data = request.json
    sender_id = data['entry'][0]['messaging'][0].get('sender', {}).get('id')
    event = data['entry'][0]['messaging'][0]
    message = event.get('message', {}).get('text')

    if sender_id not in user_conversations:
        user_conversations[sender_id] = UserConversation()

    state = user_conversations[sender_id]
    
    # Log incoming message
    app.logger.info(f'Received message from user {sender_id}: {message}')
    
    if message.lower() == 'menu':
        response = get_cached_menu()
        send_message(sender_id, response)
        return jsonify(success=True)

    elif message in non_api_messages:
        send_message(sender_id, non_api_messages[message])
        return jsonify(success=True)

    elif message.lower() == 'добре':
        response = {
            "text": prompt_user(state),
            "quick_replies": [
                {"type": "postback", "title": "Замовити", "payload": "PLACE_ORDER"},
                {"type": "postback", "title": "Запитати ще щось", "payload": "ASK_MORE"}
            ]
        }
        send_message(sender_id, response)
        return jsonify(success=True)

    elif state.context == 'order_in_progress':
        if message.isdigit() and 'amount' not in state.ordering_data:
            state.ordering_data['amount'] = int(message)
            message = prompt_user(state)
        elif 'address' not in state.ordering_data:
            state.ordering_data['address'] = message
            message = 'Ваше замовлення прийнято в роботу. Ми зв'яжемося з вами, коли замовлення буде готове до доставки.'
        
        send_message(sender_id, {"text": message})

    else:
        response_text = perplexity(message.strip())
        send_message(sender_id, response_text)

    return jsonify(success=True)

def send_message(sender, message):
    app.logger.info(f"Sending message from {API_NAME}: {message}")
    # Here you'd actually send the message to the messaging platform
        
@app.errorhandler(404)
def not_found(error):
    # Log the error
    app.logger.error(f"404 {request.path}")
    return jsonify(success=False, message="Статус замовлення не знайдено."), 404

if __name__ == '__main__':
    # In production, use Gunicorn or uWSGI 
    # app.run(host='0.0.0.0', port=5000)
    app.run(debug=False)

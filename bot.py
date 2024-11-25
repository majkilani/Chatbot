from flask import Flask, request
import requests
import os
from dotenv import load_dotenv
import json
import asyncio
from perplexity import Perplexity

# Load environment variables
load_dotenv()

app = Flask(__name__)

# Temporary storage for user sessions
user_sessions = {}

# Initialize Perplexity client
perplexity = Perplexity(api_key=os.getenv('PERPLEXITY_API_KEY'))

@app.route('/', methods=['GET'])
def verify():
    return "Bot is running!"

@app.route('/webhook', methods=['GET'])
def verify_webhook():
    if request.args.get("hub.mode") == "subscribe" and request.args.get("hub.challenge"):
        if not request.args.get("hub.verify_token") == os.getenv("VERIFY_TOKEN"):
            return "Token verification failed", 403
        return request.args["hub.challenge"], 200
    return "Hello", 200

async def get_perplexity_response(query):
    try:
        response = await perplexity.chat(query)
        return response
    except Exception as e:
        print(f"Error getting Perplexity response: {str(e)}")
        return "Sorry, I couldn't process your request at the moment."

@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.get_json()
    print("Received webhook data:", json.dumps(data, indent=2))
    
    if data["object"] != "page":
        return "ok", 200

    for entry in data["entry"]:
        for messaging_event in entry["messaging"]:
            # Skip if this is an echo of our own message
            if messaging_event.get("message", {}).get("is_echo", False):
                print("Skipping echo message")
                continue

            # Get the sender ID
            sender_id = messaging_event.get("sender", {}).get("id")
            if not sender_id:
                continue

            # Get the message text
            message = messaging_event.get("message", {})
            if not message or "text" not in message:
                continue

            message_text = message["text"].lower().strip()
            print(f"Processing message: '{message_text}' from sender: {sender_id}")

            # Handle different message types
            if message_text in ["привіт", "прівет", "hi", "hello", "добрый вечер", "привет"]:
                send_message(sender_id, "Привіт! 👋\nЩоб замовити яйця, напишіть 'замовити'\nДля довідки напишіть 'допомога'")
            elif message_text == "замовити":
                start_order(sender_id)
            elif message_text == "допомога":
                # Use Perplexity for help responses
                response = asyncio.run(get_perplexity_response(
                    "Provide a brief help message about ordering eggs in Ukrainian language"
                ))
                send_message(sender_id, response)
            elif sender_id in user_sessions:
                process_order(sender_id, message_text)
            else:
                # Use Perplexity for general responses
                response = asyncio.run(get_perplexity_response(message_text))
                send_message(sender_id, response)

    return "ok", 200

def send_message(recipient_id, message_text):
    try:
        url = f"https://graph.facebook.com/v2.6/me/messages"
        params = {"access_token": os.getenv("PAGE_ACCESS_TOKEN")}
        headers = {"Content-Type": "application/json"}
        data = {
            "recipient": {"id": recipient_id},
            "message": {"text": message_text}
        }
        
        print(f"Sending message to {recipient_id}: {message_text}")
        response = requests.post(url, params=params, headers=headers, json=data)
        print(f"Facebook API response: {response.status_code} - {response.text}")
        
        return response.ok
    except Exception as e:
        print(f"Error sending message: {str(e)}")
        return False

def start_order(sender_id):
    user_sessions[sender_id] = {
        'state': 'quantity',
        'order': {}
    }
    send_message(sender_id, "🥚 Скільки десятків яєць ви бажаєте замовити?\nБудь ласка, введіть число:")

def process_order(sender_id, message_text):
    session = user_sessions.get(sender_id)
    if not session:
        return

    state = session['state']
    
    if state == 'quantity':
        try:
            quantity = int(message_text)
            if quantity <= 0:
                send_message(sender_id, "❌ Будь ласка, введіть число більше 0")
                return
            
            session['order']['quantity'] = quantity
            session['state'] = 'phone'
            send_message(sender_id, "📱 Введіть ваш номер телефону у форматі:\n+380XXXXXXXXX")
            
        except ValueError:
            send_message(sender_id, "❌ Будь ласка, введіть правильне число")
            
    elif state == 'phone':
        if message_text.startswith('+380') and len(message_text) == 13 and message_text[1:].isdigit():
            session['order']['phone'] = message_text
            session['state'] = 'address'
            send_message(sender_id, "📍 Введіть адресу доставки:")
        else:
            send_message(sender_id, "❌ Будь ласка, введіть номер у форматі +380XXXXXXXXX")
            
    elif state == 'address':
        session['order']['address'] = message_text
        
        # Create order summary
        order = session['order']
        summary = (f"📝 Ваше замовлення:\n"
                  f"Кількість: {order['quantity']} десятків\n"
                  f"Телефон: {order['phone']}\n"
                  f"Адреса: {order['address']}\n\n"
                  f"Дякуємо за замовлення! Ми зв'яжемося з вами найближчим часом.")
        
        send_message(sender_id, summary)
        
        # Clear the session
        del user_sessions[sender_id]

if __name__ == "__main__":
    app.run(debug=True, port=5000)

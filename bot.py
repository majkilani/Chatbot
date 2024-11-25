from flask import Flask, request
import requests
import os

app = Flask(__name__)

# Temporary storage for user sessions
user_sessions = {}

@app.route('/', methods=['GET'])
def verify():
    return "Bot is running!"

@app.route('/webhook', methods=['GET'])
def verify_webhook():
    if request.args.get("hub.mode") == "subscribe" and request.args.get("hub.challenge"):
        if not request.args.get("hub.verify_token") == os.environ["VERIFY_TOKEN"]:
            return "Token verification failed", 403
        return request.args["hub.challenge"], 200
    return "Hello", 200

@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.get_json()
    print("Received data:", data)  # Debug print
    
    if data["object"] == "page":
        for entry in data["entry"]:
            for messaging_event in entry["messaging"]:
                # Skip if the message is from the page
                if messaging_event.get("message", {}).get("is_echo"):
                    continue
                    
                # Only process messages from users
                if (messaging_event.get("message") and 
                    "text" in messaging_event["message"] and 
                    "sender" in messaging_event):
                    
                    sender_id = messaging_event["sender"]["id"]
                    message_text = messaging_event["message"]["text"].lower()
                    
                    print(f"Processing message: {message_text} from sender: {sender_id}")  # Debug print
                    
                    # Handle different message types
                    if message_text in ["привіт", "прівет", "hi", "hello", "добрый вечер", "привет"]:
                        response_text = "Привіт! 👋\nЩоб замовити яйця, напишіть 'замовити'"
                        send_message(sender_id, response_text)
                    elif message_text == "замовити":
                        start_order(sender_id)
                    elif sender_id in user_sessions:
                        process_order(sender_id, message_text)
    
    return "ok", 200

def send_message(recipient_id, message_text):
    try:
        message_data = {
            "messaging_type": "RESPONSE",
            "recipient": {
                "id": recipient_id
            },
            "message": {
                "text": message_text
            }
        }

        response = requests.post(
            "https://graph.facebook.com/v2.6/me/messages",
            params={"access_token": os.environ["PAGE_ACCESS_TOKEN"]},
            json=message_data
        )
        
        print(f"Send message response: {response.status_code} {response.text}")  # Debug print
        
        if response.status_code != 200:
            print(f"Failed to send message: {response.status_code} {response.text}")
            
    except Exception as e:
        print(f"Error sending message: {str(e)}")

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
    app.run(debug=True)

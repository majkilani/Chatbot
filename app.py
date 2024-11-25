import os
from flask import Flask, request
import requests
from dotenv import load_dotenv
import json
import logging
import re
from datetime import datetime

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

load_dotenv()

app = Flask(__name__)

VERIFY_TOKEN = os.environ.get('VERIFY_TOKEN')
PAGE_ACCESS_TOKEN = os.environ.get('PAGE_ACCESS_TOKEN')
PERPLEXITY_API_KEY = os.environ.get('PERPLEXITY_API_KEY')

# Pattern matching for common queries
PATTERNS = {
    r'ціна|коштує|вартість': 'price',
    r'доставка|доставляєте': 'delivery',
    r'замовити|замовлення': 'order',
    r'час|години|працюєте': 'schedule'
}

STANDARD_RESPONSES = {
    'price': """Ціна на одне яйце залежить від кількості замовлених яєць.

Наші ціни:
- 1 лоток (20 яєць) = 50-55 гривень

Ціна включає доставку.""",
    'delivery': "Ми доставляємо по місту. Доставка безкоштовна!",
    'order': "Для замовлення, будь ласка, вкажіть:\n1. Кількість лотків\n2. Адресу доставки\n3. Бажану дату доставки",
    'schedule': "Ми працюємо з понеділка по суботу. Замовлення приймаємо за день до доставки."
}

CUSTOM_TRAINING_EXAMPLES = {
    "price_examples": [
        {
            "question": "Скільки коштують яйця?",
            "answer": """Ціна на одне яйце залежить від кількості замовлених яєць.

Наші ціни:
- 1 лоток (20 яєць) = 50-55 гривень

Ціна включає доставку."""
        },
        {
            "question": "Яка ціна за лоток?",
            "answer": "Лоток на 20 яєць коштує 50-55 гривень. Ціна включає доставку."
        }
    ],
    "delivery_examples": [
        {
            "question": "Куди ви доставляєте?",
            "answer": "Ми доставляємо по місту. Доставка безкоштовна!"
        },
        {
            "question": "Як замовити доставку?",
            "answer": "Для замовлення доставки просто напишіть нам кількість лотків, адресу та бажану дату доставки."
        }
    ],
    "order_examples": [
        {
            "question": "Як замовити яйця?",
            "answer": "Для замовлення, будь ласка, вкажіть:\n1. Кількість лотків\n2. Адресу доставки\n3. Бажану дату доставки"
        }
    ],
    "schedule_examples": [
        {
            "question": "Коли ви працюєте?",
            "answer": "Ми працюємо з понеділка по суботу. Замовлення приймаємо за день до доставки."
        }
    ]
}

def verify_page_token():
    try:
        response = requests.get(
            f"https://graph.facebook.com/debug_token",
            params={
                "input_token": PAGE_ACCESS_TOKEN,
                "access_token": PAGE_ACCESS_TOKEN
            }
        )
        logger.debug(f"Token verification response: {response.json()}")
        return response.status_code == 200
    except Exception as e:
        logger.error(f"Token verification error: {str(e)}")
        return False

def save_conversation(user_message, bot_response, feedback=None):
    conversation_data = {
        "timestamp": datetime.now().isoformat(),
        "user_message": user_message,
        "bot_response": bot_response,
        "feedback": feedback
    }
    
    try:
        with open('training_data.json', 'a', encoding='utf-8') as f:
            json.dump(conversation_data, f, ensure_ascii=False)
            f.write('\n')
    except Exception as e:
        logger.error(f"Error saving conversation: {str(e)}")

def get_perplexity_response(message):
    headers = {
        "Authorization": f"Bearer {PERPLEXITY_API_KEY}",
        "Content-Type": "application/json"
    }
    
    system_prompt = """You are a helpful Ukrainian-speaking assistant for an egg delivery service. 
    
Price information:
Ціна на одне яйце залежить від кількості замовлених яєць.
- 1 лоток (20 яєць) = 50-55 гривень
Ціна включає доставку.

Delivery information:
- Доставляємо по місту
- Безкоштовна доставка
- Працюємо з понеділка по суботу
- Замовлення приймаємо за день до доставки

Always respond in Ukrainian. Be concise but friendly."""

    data = {
        "model": "mixtral-8x7b-instruct",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": message}
        ]
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
            logger.error(f"Perplexity API error: {response.text}")
            return None
    except Exception as e:
        logger.error(f"Error calling Perplexity API: {str(e)}")
        return None

def get_response(message):
    message = message.lower()
    
    # Check pattern matching first
    for pattern, response_key in PATTERNS.items():
        if re.search(pattern, message):
            return STANDARD_RESPONSES[response_key]
    
    # If no pattern match, use Perplexity API
    ai_response = get_perplexity_response(message)
    if ai_response:
        return ai_response
    
    # Fallback response
    return "Вибачте, я не зовсім зрозумів ваше питання. Можете уточнити?"

def send_message(recipient_id, message_text):
    try:
        response = requests.post(
            "https://graph.facebook.com/v13.0/me/messages",
            params={"access_token": PAGE_ACCESS_TOKEN},
            json={
                "recipient": {"id": recipient_id},
                "message": {"text": message_text}
            }
        )
        
        if response.status_code != 200:
            logger.error(f"Failed to send message: {response.text}")
            
    except Exception as e:
        logger.error(f"Error sending message: {str(e)}")

@app.route('/', methods=['GET'])
def verify():
    if request.args.get("hub.mode") == "subscribe" and request.args.get("hub.challenge"):
        if not request.args.get("hub.verify_token") == VERIFY_TOKEN:
            return "Verification token mismatch", 403
        return request.args["hub.challenge"], 200
    return "Hello world", 200

@app.route('/', methods=['POST'])
def webhook():
    data = request.get_json()
    logger.debug(f"Received webhook data: {data}")

    if data["object"] == "page":
        for entry in data["entry"]:
            for messaging_event in entry["messaging"]:
                if messaging_event.get("message"):
                    sender_id = messaging_event["sender"]["id"]
                    message_text = messaging_event["message"].get("text", "")
                    
                    response = get_response(message_text)
                    send_message(sender_id, response)
                    save_conversation(message_text, response)

    return "ok", 200

if __name__ == '__main__':
    if verify_page_token():
        app.run(debug=True)
    else:
        logger.error("Failed to verify Facebook Page Access Token")

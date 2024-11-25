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
    'price': "Наші ціни на яйця:\n- 1 лоток (30 яєць) = 45 шекелів\n- 2 лотки (60 яєць) = 85 шекелів",
    'delivery': "Ми доставляємо в Ашкелон та Беер-Шеву. Доставка безкоштовна!",
    'order': "Для замовлення, будь ласка, вкажіть:\n1. Кількість лотків\n2. Адресу доставки\n3. Бажану дату доставки",
    'schedule': "Ми працюємо з неділі по п'ятницю. Замовлення приймаємо за день до доставки."
}

# Custom training examples
CUSTOM_TRAINING_EXAMPLES = {
    "price_examples": [
        {
            "question": "Скільки коштують яйця?",
            "answer": "Наші ціни на яйця:\n- 1 лоток (30 яєць) = 45 шекелів\n- 2 лотки (60 яєць) = 85 шекелів"
        },
        {
            "question": "Яка ціна за лоток?",
            "answer": "Один лоток (30 яєць) коштує 45 шекелів. При замовленні двох лотків - 85 шекелів."
        }
    ],
    "delivery_examples": [
        {
            "question": "Куди ви доставляєте?",
            "answer": "Ми доставляємо в Ашкелон та Беер-Шеву. Доставка безкоштовна!"
        },
        {
            "question": "Як замовити доставку?",
            "answer": "Для замовлення доставки просто напишіть нам кількість лотків, адресу та бажану дату доставки."
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

def monitor_response_quality(user_message, bot_response):
    metrics = {
        "timestamp": datetime.now().isoformat(),
        "message_length": len(user_message),
        "response_length": len(bot_response),
        "contains_price": bool(re.search(r'(\d+)\s*шекелів', bot_response)),
        "contains_delivery": bool(re.search(r'доставк', bot_response.lower())),
    }
    
    try:
        with open('response_metrics.json', 'a', encoding='utf-8') as f:
            json.dump(metrics, f, ensure_ascii=False)
            f.write('\n')
    except Exception as e:
        logger.error(f"Error saving metrics: {str(e)}")

def get_response_by_pattern(user_message):
    user_message = user_message.lower()
    for pattern, response_type in PATTERNS.items():
        if re.search(pattern, user_message):
            return STANDARD_RESPONSES[response_type]
    return None

def get_perplexity_response(user_message):
    training_messages = []
    for category in CUSTOM_TRAINING_EXAMPLES.values():
        for example in category:
            training_messages.extend([
                {"role": "user", "content": example["question"]},
                {"role": "assistant", "content": example["answer"]}
            ])

    headers = {
        "Authorization": f"Bearer {PERPLEXITY_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": "llama-3.1-sonar-small-128k-online",
        "messages": [
            {
                "role": "system",
                "content": """You are a helpful assistant for an egg business. Always respond in Ukrainian language. Use these standard responses:

                Price information / Інформація про ціни:
                "Наші ціни на яйця:
                - 1 лоток (30 яєць) = 45 шекелів
                - 2 лотки (60 яєць) = 85 шекелів
                Ціна включає доставку"

                Delivery information / Інформація про доставку:
                "Інформація про доставку:
                - Безкоштовна доставка в Ашкелон та Беер-Шеву
                - Мінімальне замовлення: 1 лоток (30 яєць)
                - Доставка: з неділі по п'ятницю
                - Замовлення потрібно робити мінімум за 1 день"

                Welcome message / Привітання:
                "Вітаємо! Ми продаємо свіжі фермерські яйця з доставкою. Чим можемо допомогти?"

                Order confirmation / Підтвердження замовлення:
                "Дякуємо за замовлення! Для підтвердження, будь ласка, вкажіть:
                1. Кількість лотків
                2. Адресу доставки
                3. Бажану дату доставки"

                Contact information / Контактна інформація:
                "Для додаткової інформації або термінових питань, звертайтесь за телефоном: [Your phone number]"

                Out of stock / Немає в наявності:
                "Вибачте, наразі всі яйця зарезервовані. Нова поставка очікується завтра."
                """
            },
            *training_messages,
            {
                "role": "user",
                "content": user_message
            }
        ],
        "temperature": 0.2,
        "top_p": 0.9
    }

    try:
        response = requests.post(
            "https://api.perplexity.ai/chat/completions",
            headers=headers,
            json=payload
        )
        
        if response.status_code == 200:
            response_data = response.json()
            return response_data['choices'][0]['message']['content']
        else:
            logger.error(f"API Error: {response.status_code}")
            return "Вибачте, виникла помилка. Спробуйте, будь ласка, пізніше."

    except Exception as e:
        logger.error(f"Error: {str(e)}")
        return "Вибачте, виникла помилка при обробці вашого запиту."

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
            "text": message_text[:2000]
        }
    }

    try:
        response = requests.post(
            "https://graph.facebook.com/v18.0/me/messages",
            params=params,
            headers=headers,
            json=data
        )
        
        if response.status_code != 200:
            logger.error(f"Failed to send message: {response.status_code}")
            return False
        return True
            
    except Exception as e:
        logger.error(f"Error sending message: {str(e)}")
        return False

def clean_training_data():
    try:
        with open('training_data.json', 'r', encoding='utf-8') as f:
            conversations = [json.loads(line) for line in f]
        
        good_conversations = [c for c in conversations if c.get('feedback') == 'good']
        
        with open('clean_training_data.json', 'w', encoding='utf-8') as f:
            for conv in good_conversations:
                json.dump(conv, f, ensure_ascii=False)
                f.write('\n')
    except Exception as e:
        logger.error(f"Error cleaning training data: {str(e)}")

@app.route('/', methods=['GET'])
def home():
    return "Egg Business Bot is running!"

@app.route('/webhook', methods=['GET'])
def verify():
    if request.args.get("hub.mode") == "subscribe" and request.args.get("hub.challenge"):
        if request.args.get("hub.verify_token") == VERIFY_TOKEN:
            return request.args.get("hub.challenge")
        return "Invalid verification token"
    return "Hello world"

@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.get_json()
    logger.debug(f"Received webhook data: {data}")
    
    if data["object"] == "page":
        for entry in data["entry"]:
            for messaging_event in entry["messaging"]:
                if messaging_event.get("message"):
                    sender_id = messaging_event["sender"]["id"]
                    
                    if "text" in messaging_event["message"]:
                        message_text = messaging_event["message"]["text"]
                        
                        # Try pattern matching first
                        response = get_response_by_pattern(message_text)
                        
                        # If no pattern match, use Perplexity
                        if not response:
                            response = get_perplexity_response(message_text)
                        
                        # Monitor response quality
                        monitor_response_quality(message_text, response)
                        
                        # Save conversation for training
                        save_conversation(message_text, response)
                        
                        # Send response
                        send_message(sender_id, response)

    return "ok", 200

@app.route('/feedback', methods=['POST'])
def feedback():
    data = request.get_json()
    save_conversation(
        data.get('user_message'),
        data.get('bot_response'),
        data.get('feedback')
    )
    return "Feedback received", 200

if __name__ == "__main__":
    if verify_page_token():
        logger.info("Page token is valid")
    else:
        logger.error("Page token is invalid")
    app.run(debug=True)

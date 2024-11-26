import os
from flask import Flask, request
import requests
from dotenv import load_dotenv
import json
import logging
import re
from typing import Dict, Optional

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

load_dotenv()

app = Flask(__name__)

VERIFY_TOKEN = os.environ.get('VERIFY_TOKEN')
PAGE_ACCESS_TOKEN = os.environ.get('PAGE_ACCESS_TOKEN')
PERPLEXITY_API_KEY = os.environ.get('PERPLEXITY_API_KEY')

class PriceInfo:
    def __init__(self, price: str, unit: str, quantity: Optional[int] = None):
        self.price = price
        self.unit = unit
        self.quantity = quantity

    def __str__(self):
        quantity_str = f" ({self.quantity} шт)" if self.quantity else ""
        return f"{self.price} грн/{self.unit}{quantity_str}"

def parse_price_from_standardized_post(message: str) -> Dict[str, PriceInfo]:
    """Parse price information from standardized posts"""
    price_info = {}
    
    # Regular expressions for price parsing
    price_pattern = r'💸\s*Ціна:\s*(\d+(?:-\d+)?)\s*грн\/(\w+)(?:\s* $(\d+)\s*шт$ )?'
    product_name_pattern = r'^([🥚🐔\w\s]+)'
    
    try:
        # Find the price information
        price_match = re.search(price_pattern, message, re.MULTILINE)
        if price_match:
            price = price_match.group(1)
            unit = price_match.group(2)
            quantity = int(price_match.group(3)) if price_match.group(3) else None
            
            # Find the product name from the first line
            first_line = message.split('\n')[0]
            product_match = re.search(product_name_pattern, first_line)
            if product_match:
                product_name = product_match.group(1).strip()
                price_info[product_name] = PriceInfo(price, unit, quantity)
    
    except Exception as e:
        logger.error(f"Error parsing price from post: {e}")
    
    return price_info

def get_latest_price_list():
    """Get the latest price list from Facebook posts"""
    try:
        url = f"https://graph.facebook.com/v18.0/me/posts"
        params = {
            "access_token": PAGE_ACCESS_TOKEN,
            "fields": "message,created_time",
            "limit": 10
        }
        
        response = requests.get(url, params=params)
        if response.status_code != 200:
            logger.error(f"Failed to fetch posts: {response.status_code}")
            return "Не вдалося отримати актуальний прайс-лист"
        
        posts = response.json().get('data', [])
        all_prices = {}
        
        for post in posts:
            message = post.get('message', '')
            if '💸 Ціна:' in message:
                prices = parse_price_from_standardized_post(message)
                all_prices.update(prices)
        
        # Format the price list
        if all_prices:
            price_list = "🏷️ Актуальний прайс-лист:\n\n"
            for product, price_info in all_prices.items():
                price_list += f"{product}: {str(price_info)}\n"
            return price_list
        else:
            return "Актуальний прайс:\n🥚 Яйця - 50-55 грн/лоток (20 шт)"
            
    except Exception as e:
        logger.error(f"Error getting price list from Facebook: {e}")
        return "Не вдалося отримати актуальний прайс-лист"

def verify_page_token():
    try:
        response = requests.get(
            "https://graph.facebook.com/debug_token",
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

@app.route('/', methods=['GET'])
def home():
    return "Bot is running!"

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
                    logger.debug(f"Sender ID: {sender_id}")
                    
                    if "text" in messaging_event["message"]:
                        message_text = messaging_event["message"]["text"]
                        logger.debug(f"Received message: {message_text}")
                        
                        # Check for price-related keywords
                        if any(keyword in message_text.lower() for keyword in ['ціна', 'прайс', 'вартість', 'почем', 'прайс-лист', 'price']):
                            response = get_latest_price_list()
                        else:
                            # Get response from Perplexity
                            response = get_perplexity_response(message_text)
                        
                        logger.debug(f"Response to send: {response}")
                        
                        # Send response back to user
                        if send_message(sender_id, response):
                            logger.debug("Message sent successfully")
                        else:
                            logger.error("Failed to send message")
    
    return "ok", 200

def get_perplexity_response(user_message):
    """Get response from Perplexity AI API"""
    headers = {
        "Authorization": f"Bearer {PERPLEXITY_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": "llama-3.1-sonar-small-128k-online",
        "messages": [
            {
                "role": "system",
                "content": "Ти - україномовний асистент. Використовуй ВИКЛЮЧНО українську мову. НЕ ВИКОРИСТОВУЙ російську мову взагалі. Вітайся так: 'Вітаю! Чим можу допомогти?'"
            },
            {
                "role": "user",
                "content": user_message
            }
        ],
        "temperature": 0.2,
        "top_p": 0.9,
        "language": "uk",
        "return_images": False,
        "return_related_questions": False
    }

    try:
        logger.debug(f"Sending request to Perplexity API: {payload}")
        response = requests.post(
            "https://api.perplexity.ai/chat/completions",
            headers=headers,
            json=payload
        )
        
        logger.debug(f"Perplexity API response status: {response.status_code}")
        logger.debug(f"Perplexity API response: {response.text}")
        
        if response.status_code == 200:
            response_data = response.json()
            return response_data['choices'][0]['message']['content']
        else:
            logger.error(f"API Error: {response.status_code}")
            logger.error(f"Response: {response.text}")
            return "Вибачте, виникла технічна помилка. Будь ласка, спробуйте пізніше."

    except Exception as e:
        logger.error(f"Error: {str(e)}")
        return "Вибачте, виникла технічна помилка. Будь ласка, спробуйте пізніше."

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
            "text": message_text[:2000]  # Facebook has a 2000 character limit
        }
    }

    logger.debug(f"Sending message to {recipient_id}: {message_text[:100]}...")

    try:
        response = requests.post(
            "https://graph.facebook.com/v18.0/me/messages",
            params=params,
            headers=headers,
            json=data
        )
        logger.debug(f"Facebook API response status: {response.status_code}")
        logger.debug(f"Facebook API response: {response.text}")
        
        if response.status_code != 200:
            logger.error(f"Failed to send message: {response.status_code}")
            logger.error(f"Response: {response.text}")
            return False
        return True
            
    except Exception as e:
        logger.error(f"Error sending message: {str(e)}")
        return False

if __name__ == "__main__":
    if verify_page_token():
        logger.info("Page token is valid")
    else:
        logger.error("Page token is invalid")
    app.run(debug=True)

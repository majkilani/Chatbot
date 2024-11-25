import os
from flask import Flask, request
import requests
from dotenv import load_dotenv
import json
import logging
import re
from datetime import datetime
from facebook_business.api import FacebookAdsApi
from facebook_business.adobjects.page import Page

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

load_dotenv()

app = Flask(__name__)

# Environment variables
VERIFY_TOKEN = os.environ.get('VERIFY_TOKEN')
PAGE_ACCESS_TOKEN = os.environ.get('PAGE_ACCESS_TOKEN')
PERPLEXITY_API_KEY = os.environ.get('PERPLEXITY_API_KEY')
PAGE_ID = os.environ.get('PAGE_ID')
FACEBOOK_APP_ID = os.environ.get('FACEBOOK_APP_ID')
FACEBOOK_APP_SECRET = os.environ.get('FACEBOOK_APP_SECRET')

# Initialize Facebook API
FacebookAdsApi.init(FACEBOOK_APP_ID, FACEBOOK_APP_SECRET, PAGE_ACCESS_TOKEN)

# Pattern matching for common queries
PATTERNS = {
    r'ціна|коштує|вартість': 'price',
    r'доставка|доставляєте': 'delivery',
    r'замовити|замовлення': 'order',
    r'час|години|працюєте': 'schedule'
}

STANDARD_RESPONSES = {
    'price': """Ціна на одне яйце залежить від кількості замовлених яєць.
    Актуальну ціну дивіться в останньому пості.""",
    'delivery': "Інформація про доставку оновлюється в наших постах.",
    'order': "Для замовлення, будь ласка, вкажіть:\n1. Кількість лотків\n2. Адресу доставки\n3. Бажану дату доставки",
    'schedule': "Ми працюємо з понеділка по суботу. Замовлення приймаємо за день до доставки."
}

class FacebookPagePosts:
    def __init__(self):
        self.page = Page(PAGE_ID)
        self.latest_post_cache = None
        self.cache_timestamp = None
        
    def get_latest_posts(self, limit=5):
        try:
            fields = [
                'message',
                'created_time',
                'attachments',
                'comments',
                'shares',
                'reactions'
            ]
            posts = self.page.get_posts(fields=fields, limit=limit)
            return list(posts)
        except Exception as e:
            logger.error(f"Error fetching posts: {str(e)}")
            return []

    def extract_price_from_post(self, post_message):
        price_pattern = r'(\d+(?:[.,]\d+)?)\s*(?:грн|гривень|грв|₴)'
        matches = re.findall(price_pattern, post_message)
        return matches[0] if matches else None

    def extract_delivery_info(self, post_message):
        delivery_patterns = [
            r'доставк[аи]\s*[:]\s*([^.\n]+)',
            r'доставляємо\s*([^.\n]+)',
            r'привеземо\s*([^.\n]+)'
        ]
        
        for pattern in delivery_patterns:
            match = re.search(pattern, post_message.lower())
            if match:
                return match.group(1).strip()
        return None

    def get_latest_post_info(self):
        posts = self.get_latest_posts(limit=1)
        if not posts:
            return None

        latest_post = posts[0]
        post_info = {
            'message': latest_post.get('message', ''),
            'created_time': latest_post.get('created_time'),
            'price': None,
            'delivery_info': None
        }

        if post_info['message']:
            post_info['price'] = self.extract_price_from_post(post_info['message'])
            post_info['delivery_info'] = self.extract_delivery_info(post_info['message'])

        return post_info

def get_current_info():
    fb_posts = FacebookPagePosts()
    latest_post = fb_posts.get_latest_post_info()
    
    if latest_post:
        price_info = latest_post['price'] if latest_post['price'] else "50-55 гривень"
        delivery_info = latest_post['delivery_info'] if latest_post['delivery_info'] else "по місту"
        
        return {
            'price': price_info,
            'delivery': delivery_info,
            'full_post': latest_post['message']
        }
    return None

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

def get_perplexity_response(message, current_info):
    headers = {
        "Authorization": f"Bearer {PERPLEXITY_API_KEY}",
        "Content-Type": "application/json"
    }
    
    system_prompt = f"""You are a helpful Ukrainian-speaking assistant for an egg delivery service. 

Latest information from our Facebook page:
{current_info['full_post'] if current_info else 'Information temporarily unavailable'}

Current Price: {current_info['price'] if current_info else '50-55 гривень за лоток'}
Delivery: {current_info['delivery'] if current_info else 'по місту'}

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
    current_info = get_current_info()
    
    # Update standard responses with current information
    if current_info:
        STANDARD_RESPONSES['price'] = f"""Актуальна ціна: {current_info['price']}

Інформація з останнього поста:
{current_info['full_post'][:200]}..."""

        STANDARD_RESPONSES['delivery'] = f"Інформація про доставку: {current_info['delivery']}"
    
    # Check pattern matching first
    for pattern, response_key in PATTERNS.items():
        if re.search(pattern, message):
            return STANDARD_RESPONSES[response_key]
    
    # If no pattern match, use Perplexity API with current information
    ai_response = get_perplexity_response(message, current_info)
    if ai_response:
        return ai_response
    
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

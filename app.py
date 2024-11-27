import os
from flask import Flask, request, jsonify
from flask_restful import Resource, Api
from dotenv import load_dotenv
from flask_cors import CORS
from functools import lru_cache

# Load environment variables
load_dotenv()

app = Flask(__name__)
cors = CORS(app)
api = Api(app)

# Configuration 
app.secret_key = os.environ.get('FLASK_SECRET_KEY', os.urandom(24))

# Mock egg types
EGG_TYPES = [
    {'id': '1', 'name': 'Черепашаче яйце', 'price': '49.99'},
    {'id': '2', 'name': 'Куряче яйце', 'price': '1.99'},
    {'id': '3', 'name': 'Страусине яйце', 'price': '15.99'},
]

class UserConversation:
    def __init__(self):
        self.active_order = None
        self.items_in_cart = []

    def set_active_order(self, order_id):
        self.active_order = order_id

user_conversations = {}


@lru_cache(maxsize=None)
def get_egg_types():
    return EGG_TYPES

class EggsComAPI(Resource):
    def __init__(self):
        super().__init__()

    def post(self):
        data = request.json
        sender_id = data.get('entry')[0]['messaging'][0]['sender']['id']
        user_message = data.get('entry')[0]['messaging'][0].get('message', {}).get('text', 'Empty').lower()

        if sender_id not in user_conversations:
            user_conversations[sender_id] = UserConversation()

        response = self.chatbot(user_message, sender_id)
        return jsonify({'response': response})

    # This method simulates a conversation with the user, returning dynamic responses based on AI services if they were integrated
    def chatbot(self, user_message, sender_id):
        if user_message == 'empty':  # Handling bot-started threads
            return self.send_quick_replies(sender_id)  # More on this later

        if 'меню' in user_message:
            return self.send_menu()
        
        elif self.add_item_to_cart(user_message, sender_id):
            return self.send_quick_replies(sender_id, confirmation=True)
        
        elif 'замовлення' in user_message:
            if not self.is_cart_empty(sender_id):
                if user_conversations[sender_id].active_order:
                    return f"Ваше замовлення з номером {user_conversations[sender_id].active_order} вже обробляється."
                else:
                    order_id = self.process_order(sender_id)
                    return self.send_order_confirmation(order_id)
            else:
                return 'Ваш кошик порожній! Додайте яйця перед тим, як оформити замовлення.'
        
        elif 'доставка' in user_message:
            return '''Звісно! Наше місто доставки - с.Хрінники, але ось ваш OTP-код для відправки на номер 380501231231: <OTP_CODE>'''
        
        elif 'купити' in user_message or 'додати' in user_message:
            return self.send_quick_replies(sender_id)
        
        else:
            return self.dynamic_response(user_message)
    
    def send_quick_replies(self, Koch - expand_if_delivery:
        return (
            {
                'text': f"Ваші яйця очікують вас у кошику.{' Використайте код ' + OTP_CODE}<OTP_CODE>}."
                if confirmation else 'Виберіть яке яйце ви хочете додати до замовлення?' + '\n1) Куряче яйце (x1) - 1.99$'
            },
            {
                'quick_replies': [
                    {'content_type': 'text', 'title': 'x1 - ' + egg['name'] + ' - ' + egg['price'] + '$', 'payload': 'item:x1'} for egg in get_egg_types()
                ]
            }
        )

    def send_menu(self):
        return {
            'text': 'Ось наші яйця в меню:', 
            'quick_replies': [
                {'content_type': 'text', 'title': '1) ' + egg['name'] + ' - ' + egg['price'], 'payload': 'item:x1'} 
                for egg in get_egg_types()
            ]
        }

    def add_item_to_cart(self, user_message, sender_id):
        for egg in get_egg_types():
            if any(egg['name'] in user_message for egg in get_egg_types()):
                user_conversations[sender_id].items_in_cart.append(egg['name'])
                return True
        return False

    def is_cart_empty(self, sender_id):
        return not user_conversations[sender_id].items_in_cart

    def process_order(self, sender_id):
        # This method would make an API call for order processing if a real payment and order management system were in place
        user_conversations[sender_id].active_order = 'ORDR' + str(len(user_conversations[sender_id].items_in_cart))
        return user_conversations[sender_id].active_order

    def send_order_confirmation(self, order_id):
        message = '''Ваше замовлення прийнято в роботу. 
        Ми зв'яжемося з вами, коли замовлення буде готове до доставки.'''
        return {'text': message, 'order_id': order_id}

    def dynamic_response(self, user_message, sender_id=None): 
        # This would call an AI service like Perplexity AI for dynamic responses
        return 'Ця функція наразі є імітуванням - ми б використовували тут Perplexity AI для динамічних відповідей.'

api.add_resource(EggsComAPI, '/webhook')

if __name__ == '__main__':
    app.run(debug=True)

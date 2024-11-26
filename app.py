import telebot
from telebot import types
import json
from datetime import datetime
import os

class Config:
    ADMIN_TELEGRAM_ID = 1334373056
    ADMIN_TELEGRAM_USERNAME = "@malkilan"
    ADMIN_NAME = "MK"
    BOT_TOKEN = 'YOUR_BOT_TOKEN'  # Replace with your actual bot token
    PRICE_PER_TRAY = 55

bot = telebot.TeleBot(Config.BOT_TOKEN)

class OrderLogger:
    def __init__(self, filename='orders.json'):
        self.filename = filename
        self.orders = self._load_orders()

    def _load_orders(self):
        if os.path.exists(self.filename):
            try:
                with open(self.filename, 'r', encoding='utf-8') as file:
                    return json.load(file)
            except:
                return []
        return []

    def _save_orders(self):
        with open(self.filename, 'w', encoding='utf-8') as file:
            json.dump(self.orders, file, ensure_ascii=False, indent=2)

    def add_order(self, order_data):
        order_id = len(self.orders) + 1
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        new_order = {
            'order_id': order_id,
            'timestamp': timestamp,
            'quantity': order_data['quantity'],
            'name': order_data['name'],
            'phone': order_data['phone'],
            'status': 'new',
            'total_cost': Config.PRICE_PER_TRAY * order_data['quantity'],
            'telegram_id': order_data.get('telegram_id')
        }
        
        self.orders.append(new_order)
        self._save_orders()
        send_order_to_admin(new_order)
        return order_id

    def get_order(self, order_id):
        for order in self.orders:
            if order['order_id'] == order_id:
                return order
        return None

    def update_order_status(self, order_id, status):
        for order in self.orders:
            if order['order_id'] == order_id:
                order['status'] = status
                self._save_orders()
                return True
        return False

order_logger = OrderLogger()

def send_order_to_admin(order_data):
    message = (
        f"🆕 NEW ORDER!\n\n"
        f"📋 Order #{order_data['order_id']}\n"
        f"📅 Date: {order_data['timestamp']}\n"
        f"👤 Name: {order_data['name']}\n"
        f"📱 Phone: {order_data['phone']}\n"
        f"📦 Quantity: {order_data['quantity']} trays\n"
        f"💰 Total: {order_data['total_cost']} UAH\n\n"
        "Use buttons below to manage order:"
    )
    
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    
    buttons = [
        types.InlineKeyboardButton("📞 Call Customer", url=f"tel:{order_data['phone']}"),
        types.InlineKeyboardButton("✅ Confirm Order", callback_data=f"confirm_{order_data['order_id']}"),
        types.InlineKeyboardButton("❌ Reject Order", callback_data=f"reject_{order_data['order_id']}"),
        types.InlineKeyboardButton("📝 Send Delivery Info", callback_data=f"msg_delivery_{order_data['order_id']}"),
        types.InlineKeyboardButton("💳 Send Payment Info", callback_data=f"msg_payment_{order_data['order_id']}")
    ]
    
    for button in buttons:
        keyboard.add(button)
    
    try:
        bot.send_message(Config.ADMIN_TELEGRAM_ID, message, reply_markup=keyboard)
    except Exception as e:
        print(f"Error sending to admin: {e}")

class UserState:
    def __init__(self):
        self.states = {}
        self.user_data = {}

    def set_state(self, user_id, state):
        self.states[user_id] = state

    def get_state(self, user_id):
        return self.states.get(user_id)

    def clear_state(self, user_id):
        if user_id in self.states:
            del self.states[user_id]
        if user_id in self.user_data:
            del self.user_data[user_id]

    def set_user_data(self, user_id, key, value):
        if user_id not in self.user_data:
            self.user_data[user_id] = {}
        self.user_data[user_id][key] = value

    def get_user_data(self, user_id):
        return self.user_data.get(user_id, {})

user_state = UserState()

@bot.message_handler(commands=['start'])
def start_handler(message):
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add(types.KeyboardButton("🛍 Place Order"))
    keyboard.add(types.KeyboardButton("ℹ️ Info"), types.KeyboardButton("📞 Contact"))
    
    welcome_message = (
        "👋 Welcome to our Egg Tray Order Bot!\n\n"
        "🥚 We offer high-quality egg trays\n"
        "💰 Price: 55 UAH per tray\n\n"
        "Choose an option below:"
    )
    
    bot.send_message(message.chat.id, welcome_message, reply_markup=keyboard)

@bot.message_handler(func=lambda message: message.text == "🛍 Place Order")
def start_order(message):
    user_state.clear_state(message.chat.id)
    user_state.set_state(message.chat.id, 'waiting_quantity')
    
    bot.send_message(
        message.chat.id,
        "📦 How many trays would you like to order?\n\nPlease enter a number:",
        reply_markup=types.ReplyKeyboardRemove()
    )

@bot.message_handler(func=lambda message: user_state.get_state(message.chat.id) == 'waiting_quantity')
def process_quantity(message):
    try:
        quantity = int(message.text)
        if quantity <= 0:
            raise ValueError
            
        user_state.set_user_data(message.chat.id, 'quantity', quantity)
        user_state.set_state(message.chat.id, 'waiting_name')
        
        total_cost = quantity * Config.PRICE_PER_TRAY
        user_state.set_user_data(message.chat.id, 'total_cost', total_cost)
        
        bot.send_message(
            message.chat.id,
            f"Total cost will be: {total_cost} UAH\n\nPlease enter your name:"
        )
    except ValueError:
        bot.send_message(message.chat.id, "Please enter a valid number!")

@bot.message_handler(func=lambda message: user_state.get_state(message.chat.id) == 'waiting_name')
def process_name(message):
    user_state.set_user_data(message.chat.id, 'name', message.text)
    user_state.set_state(message.chat.id, 'waiting_phone')
    
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add(types.KeyboardButton("📱 Share Phone Number", request_contact=True))
    
    bot.send_message(
        message.chat.id,
        "Please share your phone number:",
        reply_markup=keyboard
    )

@bot.message_handler(content_types=['contact'])
def process_contact(message):
    if user_state.get_state(message.chat.id) == 'waiting_phone':
        process_phone_number(message.chat.id, message.contact.phone_number)

@bot.message_handler(func=lambda message: user_state.get_state(message.chat.id) == 'waiting_phone')
def process_phone_text(message):
    process_phone_number(message.chat.id, message.text)

def process_phone_number(chat_id, phone):
    user_data = user_state.get_user_data(chat_id)
    user_data['phone'] = phone
    user_data['telegram_id'] = chat_id
    
    order_id = order_logger.add_order(user_data)
    
    confirmation_message = (
        f"✅ Order #{order_id} confirmed!\n\n"
        f"📦 Quantity: {user_data['quantity']} trays\n"
        f"💰 Total: {user_data['total_cost']} UAH\n"
        f"👤 Name: {user_data['name']}\n"
        f"📱 Phone: {user_data['phone']}\n\n"
        "We'll contact you shortly to confirm the order!"
    )
    
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add(types.KeyboardButton("🛍 Place Order"))
    keyboard.add(types.KeyboardButton("ℹ️ Info"), types.KeyboardButton("📞 Contact"))
    
    bot.send_message(chat_id, confirmation_message, reply_markup=keyboard)
    user_state.clear_state(chat_id)

@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    action, order_id = call.data.split('_', 1)
    order_id = int(order_id)
    
    if action == 'confirm':
        order_logger.update_order_status(order_id, 'confirmed')
        notify_customer(order_id, "✅ Your order has been confirmed! We'll contact you shortly with delivery details.")
        message = "✅ Order confirmed"
        
    elif action == 'reject':
        order_logger.update_order_status(order_id, 'rejected')
        notify_customer(order_id, "❌ Sorry, we cannot process your order at this time.")
        message = "❌ Order rejected"
        
    elif action == 'msg_delivery':
        send_delivery_info(order_id)
        message = "📬 Delivery info sent"
        
    elif action == 'msg_payment':
        send_payment_info(order_id)
        message = "💳 Payment info sent"
    
    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text=call.message.text + f"\n\n{message}",
        reply_markup=call.message.reply_markup
    )

def notify_customer(order_id, message):
    order = order_logger.get_order(order_id)
    if order and order.get('telegram_id'):
        try:
            bot.send_message(order['telegram_id'], message)
        except Exception as e:
            print(f"Error notifying customer: {e}")

def send_delivery_info(order_id):
    order = order_logger.get_order(order_id)
    delivery_message = (
        "🚚 Delivery Information:\n\n"
        "1. We'll contact you to confirm delivery time\n"
        "2. Please prepare exact amount for payment\n"
        "3. Delivery area: Within city limits\n"
        "4. Estimated delivery time: 2-3 hours\n\n"
        "Questions? Contact us!"
    )
    notify_customer(order_id, delivery_message)

def send_payment_info(order_id):
    order = order_logger.get_order(order_id)
    payment_message = (
        "💳 Payment Information:\n\n"
        "1. Cash on delivery\n"
        "2. Please prepare exact amount\n"
        f"3. Total amount: {order['total_cost']} UAH\n\n"
        "Questions? Contact us!"
    )
    notify_customer(order_id, payment_message)

@bot.message_handler(commands=['test_admin'])
def test_admin_notification(message):
    if message.from_user.id == Config.ADMIN_TELEGRAM_ID:
        test_order = {
            'order_id': 'TEST-001',
            'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'name': 'Test Customer',
            'phone': '+380953314400',
            'quantity': 2,
            'total_cost': 110
        }
        send_order_to_admin(test_order)
        bot.reply_to(message, "Test notification sent!")

@bot.message_handler(func=lambda message: message.text == "ℹ️ Info")
def info_handler(message):
    info_message = (
        "ℹ️ About Our Egg Trays:\n\n"
        "🥚 High-quality egg trays\n"
        "💰 Price: 55 UAH per tray\n"
        "🚚 Delivery available\n"
        "💳 Cash on delivery\n\n"
        "For more information, contact us!"
    )
    bot.send_message(message.chat.id, info_message)

@bot.message_handler(func=lambda message: message.text == "📞 Contact")
def contact_handler(message):
    contact_message = (
        "📞 Contact Information:\n\n"
        "☎️ Phone: +380953314400\n"
        "👤 Manager: MK\n"
        "⏰ Working hours: 9:00 - 18:00\n\n"
        "Feel free to contact us!"
    )
    bot.send_message(message.chat.id, contact_message)

if __name__ == "__main__":
    print("Bot started...")
    bot.polling(none_stop=True)

import os
import sys
import threading
import django
from flask import Flask, request, abort
from dotenv import load_dotenv
import telebot

from django.utils import timezone
from datetime import datetime, timedelta

# --- Django Setup ---
# Add the project root to the Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.append(project_root)

# Load environment variables
dotenv_path = os.path.join(project_root, '.env')
load_dotenv(dotenv_path)

# Set the Django settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')

# Initialize Django
django.setup()

from backend.models import User, Order
# -- End Django Setup --

# --- Bot Initialization ---
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
CHANNEL_ID = os.getenv('CHANNEL_ID')
# Get the base URL of the website from environment variables for use in messages
WEBSITE_URL = os.getenv('RENDER_EXTERNAL_URL', 'http://localhost:8000')

if not TELEGRAM_TOKEN or not CHANNEL_ID:
    raise ValueError("TELEGRAM_TOKEN and CHANNEL_ID must be set in the .env file.")

bot = telebot.TeleBot(TELEGRAM_TOKEN)
# --- End Bot Initialization ---


# --- Flask Webhook Listener ---
# This small web server listens for notifications from the Django app
app = Flask(__name__)

@app.route('/notify', methods=['POST'])
def notify_from_django():
    data = request.get_json()
    if not data:
        abort(400, 'Invalid JSON')

    notification_type = data.get('type')

    if notification_type == 'order_taken':
        username = data.get('username')
        order_title = data.get('order_title')
        deadline_str = data.get('deadline')
        deadline = datetime.fromisoformat(deadline_str).strftime('%d %B %Y, %H:%M')
        
        message = f"🏴‍☠️ Пират @{username} вызвал на бой за заказ: *{order_title}*\n\n⏰ Срок: до {deadline}"
        bot.send_message(CHANNEL_ID, message, parse_mode='Markdown')
    
    return 'Notification received', 200

def run_flask_app():
    # Use a fixed internal port that does not conflict with Gunicorn
    port = 8001 
    app.run(host='0.0.0.0', port=port)
# --- End Flask Webhook Listener ---


# --- Telegram Command Handlers ---
@bot.message_handler(commands=['start'])
def start(message):
    try:
        user = User.objects.get(telegram_id=message.from_user.id)
        reply_text = f"С возвращением, {user.username}! Рад снова вас видеть."
        bot.reply_to(message, reply_text)
    except User.DoesNotExist:
        reply_text = (
            f"Добро пожаловать, новый пират!\n\n"
            f"Чтобы начать, вам нужно зарегистрироваться на нашем сайте, а затем привязать свой Telegram-аккаунт.\n\n"
            f"1. Зарегистрируйтесь здесь: {WEBSITE_URL}/accounts/signup/\n"
            f"2. После регистрации зайдите в свой профиль на сайте и следуйте инструкциям по привязке."
        )
        bot.reply_to(message, reply_text, disable_web_page_preview=True)

@bot.message_handler(commands=['link'])
def link(message):
    try:
        token = message.text.split()[1]
    except IndexError:
        bot.reply_to(message, "Неверный формат. Используйте команду, скопированную из вашего профиля на сайте.")
        return

    try:
        user = User.objects.get(telegram_link_token=token)
        token_lifetime = timedelta(minutes=15)

        if user.token_generated_at and timezone.now() > user.token_generated_at + token_lifetime:
            bot.reply_to(message, "Этот код для привязки истек. Пожалуйста, получите новый код в вашем профиле на сайте.")
            return
        
        if user.telegram_id:
            bot.reply_to(message, f"Этот аккаунт уже привязан к другому пользователю Telegram (@{user.username}). Если это ошибка, обратитесь к администратору.")
            return

        user.telegram_id = message.from_user.id
        user.telegram_link_token = None # Deactivate the token
        user.save()
        bot.reply_to(message, f"✅ Отлично, {user.username}! Ваш Telegram-аккаунт успешно привязан.")

    except User.DoesNotExist:
        bot.reply_to(message, "Неверный код привязки. Пожалуйста, скопируйте команду из вашего профиля на сайте еще раз.")


@bot.message_handler(commands=['info'])
def info(message):
    try:
        user = User.objects.get(telegram_id=message.from_user.id)
        reply_text = f"🏴‍☠️ *Профиль пирата*\n\n👤 Имя: @{user.username}\n💰 Очки: {user.points}"
        bot.reply_to(message, reply_text, parse_mode='Markdown')
    except User.DoesNotExist:
        bot.reply_to(message, "Вы не зарегистрированы. Используйте /start для регистрации.")

@bot.message_handler(commands=['orders'])
def list_orders(message):
    active_orders = Order.objects.filter(status='active').order_by('deadline')
    if not active_orders:
        bot.reply_to(message, "На данный момент нет активных заказов.")
        return

    reply_text = "*📜 Активные заказы:*"
    bot.reply_to(message, reply_text, parse_mode='Markdown')

@bot.message_handler(commands=['my_orders'])
def my_orders(message):
    try:
        user = User.objects.get(telegram_id=message.from_user.id)
        taken_orders = Order.objects.filter(taken_by=user, status='taken')
        
        if not taken_orders:
            bot.reply_to(message, "У вас нет активных заказов. Возьмите один на сайте!")
            return

        reply_text = "*💀 Ваши взятые заказы:*"
        for order in taken_orders:
            reply_text += f"*ID: {order.id}* | *{order.title}*\n⏰ Срок: {order.deadline.strftime('%d.%m.%Y %H:%M')}\n\n"
        reply_text += "Чтобы завершить заказ, используйте команду `/complete <ID>`."
        bot.reply_to(message, reply_text, parse_mode='Markdown')

    except User.DoesNotExist:
        bot.reply_to(message, "Вы не зарегистрированы. Используйте /start.")

@bot.message_handler(commands=['complete'])
def complete_order(message):
    try:
        parts = message.text.split()
        if len(parts) < 2 or not parts[1].isdigit():
            bot.reply_to(message, "Неверный формат. Используйте: `/complete <ID заказа>`")
            return
        
        order_id = int(parts[1])
        user = User.objects.get(telegram_id=message.from_user.id)
        
        order = Order.objects.get(pk=order_id, taken_by=user, status='taken')
        
        # Update order and user points
        order.status = 'completed'
        order.save()
        user.points += order.reward
        user.save()

        # Notify user
        bot.reply_to(message, f'🎉 Отлично! Заказ "{order.title}" выполнен. Вам начислено {order.reward} очков.')

        # Notify channel
        channel_message = f"✅ Пират @{user.username} выполнил заказ: *{order.title}*\n\n💰 Награда: {order.reward} berries"
        bot.send_message(CHANNEL_ID, channel_message, parse_mode='Markdown')

    except User.DoesNotExist:
        bot.reply_to(message, "Вы не зарегистрированы. Используйте /start.")
    except Order.DoesNotExist:
        bot.reply_to(message, "Заказ с таким ID не найден среди ваших активных заказов.")
    except Exception as e:
        bot.reply_to(message, f"Произошла ошибка: {e}")
# --- End Command Handlers ---


if __name__ == '__main__':
    print("Starting Flask webhook listener in a background thread...")
    flask_thread = threading.Thread(target=run_flask_app)
    flask_thread.daemon = True
    flask_thread.start()

    print("Starting Telegram bot polling...")
    bot.polling(none_stop=True)

import os
import sys
import threading
import django
from flask import Flask, request, abort
from dotenv import load_dotenv
import telebot

from datetime import datetime

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
    # Listens on 0.0.0.0 to be accessible in containers. Port is configured for Render.
    port = int(os.environ.get('PORT', 8001))
    app.run(host='0.0.0.0', port=port)
# --- End Flask Webhook Listener ---


# --- Telegram Command Handlers ---
@bot.message_handler(commands=['start'])
def start(message):
    telegram_id = message.from_user.id
    username = message.from_user.username

    if not username:
        bot.reply_to(message, "Пожалуйста, установите username в настройках вашего Telegram аккаунта, чтобы зарегистрироваться.")
        return

    # Find or create the Django user
    user, created = User.objects.get_or_create(
        telegram_id=telegram_id,
        defaults={'username': username}
    )

    if created:
        reply_text = f"Добро пожаловать, пират @{username}! Вы были успешно зарегистрированы на доске заказов."
    else:
        reply_text = f"С возвращением, @{username}! Рад снова вас видеть."
    
    bot.reply_to(message, reply_text)

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

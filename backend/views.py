from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.utils import timezone
import requests
import os

from django.utils import timezone
import uuid
from datetime import timedelta

from .models import Order, User
from .forms import CustomUserCreationForm

def signup(request):
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('login')
    else:
        form = CustomUserCreationForm()
    return render(request, 'registration/signup.html', {'form': form})

@login_required
def profile(request):
    user = request.user
    token_lifetime = timedelta(minutes=15)
    
    # Generate a new token if the user doesn't have one or if it has expired
    if not user.telegram_link_token or (user.token_generated_at and timezone.now() > user.token_generated_at + token_lifetime):
        user.telegram_link_token = uuid.uuid4()
        user.token_generated_at = timezone.now()
        user.save()

    link_command = f"/link {user.telegram_link_token}"

    return render(request, 'profile.html', {'link_command': link_command})

def index(request):
    # Update expired orders first
    Order.objects.filter(deadline__lt=timezone.now(), status='active').update(status='expired')
    
    active_orders = Order.objects.filter(status='active').order_by('deadline')
    return render(request, 'index.html', {'orders': active_orders})

def order_detail(request, order_id):
    order = get_object_or_404(Order, pk=order_id)
    return render(request, 'order_detail.html', {'order': order})

@login_required
@transaction.atomic
def take_order(request, order_id):
    if request.method == 'POST':
        order = get_object_or_404(Order, pk=order_id)

        if order.status != 'active':
            return JsonResponse({'status': 'error', 'message': 'Этот заказ уже недоступен.'}, status=400)

        if order.deadline < timezone.now():
            order.status = 'expired'
            order.save()
            return JsonResponse({'status': 'error', 'message': 'Срок выполнения этого заказа истек.'}, status=400)

        order.status = 'taken'
        order.taken_by = request.user
        order.save()

        # --- Improved Bot Notification Logic ---
        bot_url = os.getenv('BOT_LISTENER_URL')
        notification_sent = False
        notification_error = None

        if bot_url:
            print(f"Attempting to notify bot at: {bot_url}")
            try:
                payload = {
                    'type': 'order_taken',
                    'username': request.user.username,
                    'order_title': order.title,
                    'deadline': order.deadline.isoformat()
                }
                response = requests.post(bot_url, json=payload, timeout=5) # 5 second timeout
                response.raise_for_status()  # Raise an HTTPError for bad responses (4xx or 5xx)
                notification_sent = True
                print("Successfully notified bot.")
            except requests.exceptions.RequestException as e:
                notification_error = str(e)
                print(f"!!! FAILED to notify bot: {notification_error}")
        else:
            notification_error = "BOT_LISTENER_URL environment variable not set."
            print(f"!!! ERROR: {notification_error}")

        return JsonResponse({
            'status': 'success',
            'message': f'Вы приняли заказ "{order.title}"! ',
            'notification_sent': notification_sent,
            'notification_error': notification_error
        })
    
    return JsonResponse({'status': 'error', 'message': 'Invalid request'}, status=400)

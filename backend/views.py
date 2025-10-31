from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.utils import timezone
import requests
import os

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

        # Notify the bot
        bot_url = os.getenv('BOT_LISTENER_URL')
        if bot_url:
            try:
                payload = {
                    'type': 'order_taken',
                    'username': request.user.username,
                    'order_title': order.title,
                    'deadline': order.deadline.isoformat()
                }
                requests.post(bot_url, json=payload, timeout=5)
            except requests.RequestException as e:
                # Log the error but don't fail the user request
                print(f"Could not notify bot: {e}")

        return JsonResponse({'status': 'success', 'message': f'Вы приняли заказ "{order.title}"!'})
    
    return JsonResponse({'status': 'error', 'message': 'Invalid request'}, status=400)

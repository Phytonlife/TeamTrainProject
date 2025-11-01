from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone

class User(AbstractUser):
    telegram_id = models.BigIntegerField(unique=True, null=True, blank=True, verbose_name='Telegram ID')
    points = models.IntegerField(default=0, verbose_name='Награда')
    telegram_link_token = models.UUIDField(null=True, blank=True, verbose_name='Токен для привязки Telegram')
    token_generated_at = models.DateTimeField(null=True, blank=True, verbose_name='Время генерации токена')

    def __str__(self):
        return self.username

class Order(models.Model):
    STATUS_CHOICES = (
        ('active', 'Активен'),
        ('taken', 'Взят'),
        ('completed', 'Выполнен'),
        ('expired', 'Просрочен'),
    )

    title = models.CharField(max_length=200, verbose_name='Название')
    description = models.TextField(verbose_name='Описание')
    reward = models.IntegerField(verbose_name='Награда (Berries)')
    deadline = models.DateTimeField(verbose_name='Срок выполнения')
    image = models.ImageField(upload_to='orders/', blank=True, null=True, verbose_name='Изображение')
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='active', verbose_name='Статус')
    taken_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='orders_taken', verbose_name='Кто взял')
    created_at = models.DateTimeField(auto_now_add=True)

    def is_past_due(self):
        return timezone.now() > self.deadline

    def __str__(self):
        return self.title

    class Meta:
        verbose_name = 'Заказ'
        verbose_name_plural = 'Заказы'
        ordering = ['-created_at']

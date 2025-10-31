from django.contrib import admin
from .models import User, Order

class UserAdmin(admin.ModelAdmin):
    list_display = ('username', 'telegram_id', 'points', 'is_staff')
    search_fields = ('username', 'telegram_id')

class OrderAdmin(admin.ModelAdmin):
    list_display = ('title', 'reward', 'status', 'taken_by', 'deadline', 'is_past_due')
    list_filter = ('status', 'deadline')
    search_fields = ('title', 'description')
    actions = ['mark_as_active']

    def mark_as_active(self, request, queryset):
        queryset.update(status='active', taken_by=None)
    mark_as_active.short_description = "Сделать активными и сбросить исполнителя"

admin.site.register(User, UserAdmin)
admin.site.register(Order, OrderAdmin)

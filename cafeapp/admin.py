
from django.contrib import admin
from django.utils import timezone

from .models import Table, Category, MenuItem, Order, OrderItem


@admin.register(Table)
class TableAdmin(admin.ModelAdmin):
    list_display = ("id", "table_number", "is_active")
    list_filter = ("is_active",)
    search_fields = ("table_number",)


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("id", "name")
    search_fields = ("name",)


@admin.register(MenuItem)
class MenuItemAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "name",
        "category",
        "price",
        "is_available",
    )
    list_filter = ("category", "is_available")
    search_fields = ("name", "description")


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ("price",)


@admin.action(description="Verify payment and mark selected orders as Paid")
def mark_orders_paid(modeladmin, request, queryset):
    updated = queryset.exclude(
        payment_status="paid"
    ).update(
        payment_status="paid",
        payment_verified_at=timezone.now(),
    )

    modeladmin.message_user(
        request,
        f"{updated} order(s) marked as Paid."
    )


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "table",
        "total_amount",
        "status",
        "payment_method",
        "payment_status",
        "payment_verified_at",
        "order_time",
    )

    list_filter = (
        "status",
        "payment_method",
        "payment_status",
        "order_time",
        "payment_verified_at",
    )

    search_fields = (
        "id",
        "table__table_number",
    )

    inlines = [OrderItemInline]

    readonly_fields = (
        "order_time",
        "payment_verified_at",
    )

    list_editable = (
        "status",
    )

    actions = [mark_orders_paid]

    ordering = ("-order_time",)


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "order",
        "menu_item",
        "quantity",
        "price",
    )

    search_fields = (
        "menu_item__name",
        "order__id",
    )

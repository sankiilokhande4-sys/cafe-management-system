from django.contrib import admin
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


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "table",
        "total_amount",
        "status",
        "order_time",
    )

    list_filter = (
        "status",
        "order_time",
    )

    search_fields = (
        "id",
        "table__table_number",
    )

    inlines = [OrderItemInline]

    readonly_fields = (
        "order_time",
    )

    list_editable = (
        "status",
    )


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
from django.db import models


class Table(models.Model):
    table_number = models.PositiveIntegerField(unique=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"Table {self.table_number}"


class Category(models.Model):
    LAYOUT_CHOICES = [
        ("auto", "Automatic"),
        ("list", "List card"),
        ("grid", "Grid card"),
        ("big", "Big card"),
    ]

    name = models.CharField(max_length=100)
    image = models.ImageField(upload_to="categories/", blank=True, null=True)
    order = models.PositiveIntegerField(default=0)
    layout = models.CharField(
        max_length=10,
        choices=LAYOUT_CHOICES,
        default="auto"
    )

    class Meta:
        ordering = ["order", "name"]

    def __str__(self):
        return self.name


class MenuItem(models.Model):
    category = models.ForeignKey(
        Category,
        on_delete=models.CASCADE,
        related_name="menu_items"
    )
    name = models.CharField(max_length=150)
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    image = models.ImageField(upload_to="menu/", blank=True, null=True)
    is_available = models.BooleanField(default=True)
    is_veg = models.BooleanField(default=True)
    is_bestseller = models.BooleanField(default=False)

    def __str__(self):
        return self.name


class Banner(models.Model):
    title = models.CharField(max_length=80)
    subtitle = models.CharField(max_length=120, blank=True)
    tag = models.CharField(max_length=30, blank=True)
    image = models.ImageField(upload_to="banners/", blank=True, null=True)
    order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["order"]

    def __str__(self):
        return self.title


class Order(models.Model):

    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("preparing", "Preparing"),
        ("ready", "Ready"),
        ("completed", "Completed"),
        ("cancelled", "Cancelled"),
    ]

    table = models.ForeignKey(
        Table,
        on_delete=models.CASCADE,
        related_name="orders"
    )
    total_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="pending"
    )
    order_time = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Order #{self.id} - Table {self.table.table_number}"

class OrderItem(models.Model):
    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name="items"
    )

    menu_item = models.ForeignKey(
        MenuItem,
        on_delete=models.CASCADE
    )

    quantity = models.PositiveIntegerField(default=1)

    price = models.DecimalField(
        max_digits=10,
        decimal_places=2
    )

    customization = models.JSONField(
        default=dict,
        blank=True
    )

    customization_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0
    )

    @property
    def subtotal(self):
        return self.quantity * (
            self.price + self.customization_price
        )

    def __str__(self):
        return f"{self.menu_item.name} x {self.quantity}"
    
   

from decimal import Decimal
from io import BytesIO

import qrcode

from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import user_passes_test
from django.db.models import Prefetch
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from .models import Table, Category, MenuItem, Order, Banner


# =========================
# AUTHENTICATION
# =========================

def admin_login(request):
    if request.user.is_authenticated and request.user.is_staff:
        return redirect("admin_dashboard")

    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        password = request.POST.get("password", "")

        user = authenticate(
            request,
            username=username,
            password=password
        )

        if user is not None and user.is_staff:
            login(request, user)
            return redirect("admin_dashboard")

        return render(
            request,
            "cafeapp/admin_login.html",
            {"error": "Invalid username or password."}
        )

    return render(request, "cafeapp/admin_login.html")


def admin_logout(request):
    logout(request)
    return redirect("admin_login")


def home(request):
    return render(request, "cafeapp/home.html")


def is_admin_user(user):
    return user.is_authenticated and user.is_staff


# =========================
# MENU
# =========================

def menu(request, table_id):
    table = get_object_or_404(
        Table,
        table_number=table_id,
        is_active=True
    )

    categories = Category.objects.prefetch_related(
        Prefetch(
            "menu_items",
            queryset=MenuItem.objects.filter(is_available=True)
        )
    ).order_by("order", "name")

    banners = Banner.objects.filter(is_active=True)

    cart_data = request.session.get("cart", {})
    cart_count = sum(int(qty) for qty in cart_data.values())
    cart_total = Decimal("0.00")

    if cart_data:
        items = MenuItem.objects.filter(
            id__in=cart_data.keys(),
            is_available=True
        )

        for item in items:
            cart_total += item.price * int(
                cart_data.get(str(item.id), 0)
            )

    return render(
        request,
        "cafeapp/menu.html",
        {
            "table": table,
            "categories": categories,
            "banners": banners,
            "cart_count": cart_count,
            "cart_total": cart_total,
        }
    )


# =========================
# CART CUSTOMIZATION CONFIG
# =========================

def get_customization_config(item):
    category_name = item.category.name if item.category else ""
    name = f"{item.name} {category_name}".lower()

    if "pizza" in name:
        return {
            "type": "pizza",
            "sizes": {
                "Regular": Decimal("0.00"),
                "Medium": Decimal("80.00"),
                "Large": Decimal("150.00"),
            },
            "cheese_price": Decimal("40.00"),
            "toppings_price": Decimal("30.00"),
        }

    if "burger" in name:
        return {
            "type": "burger",
            "cheese_price": Decimal("25.00"),
        }

    if any(word in name for word in [
        "coffee", "tea", "chai", "latte", "cappuccino"
    ]):
        return {
            "type": "drink",
            "large_price": Decimal("30.00"),
            "extra_milk_price": Decimal("15.00"),
        }

    return {"type": "other"}


# =========================
# ADD TO CART
# =========================

@require_POST
def add_to_cart(request, table_id, item_id):
    table = get_object_or_404(
        Table,
        table_number=table_id,
        is_active=True
    )

    item = get_object_or_404(
        MenuItem,
        id=item_id,
        is_available=True
    )

    cart_data = request.session.get("cart", {})
    key = str(item.id)

    cart_data[key] = int(cart_data.get(key, 0)) + 1

    request.session["cart"] = cart_data
    request.session["cart_table"] = table.table_number

    return redirect("cart", table_id=table.table_number)


# =========================
# VIEW CART
# =========================

def cart(request, table_id):
    table = get_object_or_404(
        Table,
        table_number=table_id,
        is_active=True
    )

    cart_data = request.session.get("cart", {})
    saved_options = request.session.get("cart_options", {})

    menu_items = MenuItem.objects.filter(
        id__in=cart_data.keys(),
        is_available=True
    ).select_related("category")

    cart_items = []
    total = Decimal("0.00")

    for item in menu_items:
        key = str(item.id)
        quantity = int(cart_data.get(key, 0))

        if quantity <= 0:
            continue

        config = get_customization_config(item)
        selected = saved_options.get(key, {})
        extra = Decimal("0.00")

        if config["type"] == "pizza":
            size = selected.get("size", "Regular")

            if size not in config["sizes"]:
                size = "Regular"

            extra += config["sizes"][size]

            if selected.get("extra_cheese"):
                extra += config["cheese_price"]

            if selected.get("toppings"):
                extra += config["toppings_price"]

        elif config["type"] == "burger":
            if selected.get("extra_cheese"):
                extra += config["cheese_price"]

        elif config["type"] == "drink":
            if selected.get("size") == "Large":
                extra += config["large_price"]

            if selected.get("extra_milk"):
                extra += config["extra_milk_price"]

        unit_price = item.price + extra
        subtotal = unit_price * quantity
        total += subtotal

        cart_items.append({
            "item": item,
            "quantity": quantity,
            "subtotal": subtotal,
            "unit_price": unit_price,
            "extra_price": extra,
            "config": config,
            "selected": selected,
        })

    return render(
        request,
        "cafeapp/cart.html",
        {
            "table": table,
            "cart_items": cart_items,
            "total": total,
        }
    )


# =========================
# QUANTITY CONTROLS
# =========================

@require_POST
def increase_quantity(request, table_id, item_id):
    table = get_object_or_404(
        Table,
        table_number=table_id,
        is_active=True
    )

    item = get_object_or_404(
        MenuItem,
        id=item_id,
        is_available=True
    )

    cart_data = request.session.get("cart", {})
    key = str(item.id)

    cart_data[key] = int(cart_data.get(key, 0)) + 1
    request.session["cart"] = cart_data

    return redirect("cart", table_id=table.table_number)


@require_POST
def decrease_quantity(request, table_id, item_id):
    table = get_object_or_404(
        Table,
        table_number=table_id,
        is_active=True
    )

    item = get_object_or_404(
        MenuItem,
        id=item_id,
        is_available=True
    )

    cart_data = request.session.get("cart", {})
    key = str(item.id)

    if key in cart_data:
        quantity = int(cart_data[key]) - 1

        if quantity <= 0:
            del cart_data[key]
        else:
            cart_data[key] = quantity

        request.session["cart"] = cart_data

    return redirect("cart", table_id=table.table_number)



def remove_from_cart(request, table_id, item_id):
    table = get_object_or_404(
        Table,
        table_number=table_id,
        is_active=True
    )

    cart_data = request.session.get("cart", {})
    key = str(item_id)

    cart_data.pop(key, None)
    request.session["cart"] = cart_data

    saved_options = request.session.get("cart_options", {})
    saved_options.pop(key, None)
    request.session["cart_options"] = saved_options

    request.session.modified = True

    return redirect("cart", table_id=table.table_number)

# =========================
# SAVE ITEM CUSTOMIZATION
# =========================

@require_POST
def save_customization(request, table_id, item_id):
    table = get_object_or_404(
        Table,
        table_number=table_id,
        is_active=True
    )

    item = get_object_or_404(
        MenuItem,
        id=item_id,
        is_available=True
    )

    cart_data = request.session.get("cart", {})
    key = str(item.id)

    if key not in cart_data:
        return redirect("cart", table_id=table.table_number)

    config = get_customization_config(item)

    size = request.POST.get("size", "Regular")
    spicy = request.POST.get("spicy", "Medium")
    sugar = request.POST.get("sugar", "Normal")

    if spicy not in ["Mild", "Medium", "Hot"]:
        spicy = "Medium"

    if sugar not in ["No Sugar", "Less", "Normal", "Extra"]:
        sugar = "Normal"

    selected = {
        "spicy": spicy,
        "sugar": sugar,
        "extra_cheese": request.POST.get("extra_cheese") == "on",
        "toppings": request.POST.get("toppings") == "on",
        "extra_milk": request.POST.get("extra_milk") == "on",
        "notes": request.POST.get("notes", "").strip()[:250],
    }

    if config["type"] == "pizza":
        if size not in config["sizes"]:
            size = "Regular"
        selected["size"] = size

    elif config["type"] == "drink":
        if size not in ["Regular", "Large"]:
            size = "Regular"
        selected["size"] = size

    else:
        selected["size"] = "Regular"

    saved_options = request.session.get("cart_options", {})
    saved_options[key] = selected

    request.session["cart_options"] = saved_options
    request.session.modified = True

    return redirect("cart", table_id=table.table_number)


# =========================
# PLACE ORDER
# =========================


@require_POST
def place_order(request, table_id):
    table = get_object_or_404(
        Table,
        table_number=table_id,
        is_active=True
    )

    # Get payment method selected by the customer
    payment_method = request.POST.get(
        "payment_method", "cash"
    ).lower()

    if payment_method not in ["cash", "upi"]:
        payment_method = "cash"

    cart_data = request.session.get("cart", {})
    saved_options = request.session.get("cart_options", {})

    if not cart_data:
        return redirect("cart", table_id=table.table_number)

    menu_items = MenuItem.objects.filter(
        id__in=cart_data.keys(),
        is_available=True
    ).select_related("category")

    if not menu_items.exists():
        return redirect("cart", table_id=table.table_number)

    from .models import OrderItem

    order = Order.objects.create(
        table=table,
        total_amount=Decimal("0.00"),
        payment_method=payment_method,
        payment_status="unpaid",
    )

    total = Decimal("0.00")

    for item in menu_items:
        quantity = int(cart_data.get(str(item.id), 0))

        if quantity <= 0:
            continue

        config = get_customization_config(item)
        selected = saved_options.get(str(item.id), {})
        extra = Decimal("0.00")

        if config["type"] == "pizza":
            size = selected.get("size", "Regular")

            if size not in config["sizes"]:
                size = "Regular"

            extra += config["sizes"][size]

            if selected.get("extra_cheese"):
                extra += config["cheese_price"]

            if selected.get("toppings"):
                extra += config["toppings_price"]

        elif config["type"] == "burger":
            if selected.get("extra_cheese"):
                extra += config["cheese_price"]

        elif config["type"] == "drink":
            if selected.get("size") == "Large":
                extra += config["large_price"]

            if selected.get("extra_milk"):
                extra += config["extra_milk_price"]

        unit_price = item.price + extra

        OrderItem.objects.create(
            order=order,
            menu_item=item,
            quantity=quantity,
            price=unit_price,
        )

        total += unit_price * quantity

    order.total_amount = total
    order.save()

    # Clear cart after successful order placement
    request.session["cart"] = {}
    request.session["cart_options"] = {}

    # Keep this order in the current customer's session
    order_ids = request.session.get("my_order_ids", [])

    if order.id not in order_ids:
        order_ids.append(order.id)

    request.session["my_order_ids"] = order_ids
    request.session["last_order_id"] = order.id
    request.session.modified = True

    return redirect(
        "order_success",
        table_id=table.table_number,
        order_id=order.id
    )


# =========================
# ORDER SUCCESS / STATUS
# =========================

def order_success(request, table_id, order_id):
    table = get_object_or_404(
        Table,
        table_number=table_id,
        is_active=True
    )

    order = get_object_or_404(
        Order,
        id=order_id,
        table=table
    )

    return render(
        request,
        "cafeapp/order_success.html",
        {"table": table, "order": order}
    )




# =========================
# ADMIN DASHBOARD
# =========================

@user_passes_test(is_admin_user, login_url="/admin-login/")
def admin_dashboard(request):
    pending_orders = Order.objects.filter(status="pending").count()
    preparing_orders = Order.objects.filter(status="preparing").count()
    ready_orders = Order.objects.filter(status="ready").count()
    completed_orders = Order.objects.filter(status="completed").count()

    recent_orders = Order.objects.select_related(
        "table"
    ).order_by("-order_time")[:10]

    return render(
        request,
        "cafeapp/admin_dashboard.html",
        {
            "pending_orders": pending_orders,
            "preparing_orders": preparing_orders,
            "ready_orders": ready_orders,
            "completed_orders": completed_orders,
            "recent_orders": recent_orders,
        }
    )


def admin_orders(request):
    if request.method == "POST":
        order_id = request.POST.get("order_id")
        new_status = request.POST.get("status")

        valid_statuses = [
            "pending", "preparing", "ready",
            "completed", "cancelled"
        ]

        if new_status in valid_statuses:
            order = get_object_or_404(Order, id=order_id)
            order.status = new_status
            order.save()

        return redirect("admin_orders")

    status_filter = request.GET.get("status")

    orders = Order.objects.select_related(
        "table"
    ).order_by("-order_time")

    valid_statuses = [
        "pending", "preparing", "ready",
        "completed", "cancelled"
    ]

    if status_filter in valid_statuses:
        orders = orders.filter(status=status_filter)

    return render(
        request,
        "cafeapp/admin_orders.html",
        {
            "orders": orders,
            "status_filter": status_filter,
        }
    )


def admin_order_detail(request, order_id):
    order = get_object_or_404(Order, id=order_id)

    if request.method == "POST":
        new_status = request.POST.get("status")

        valid_statuses = [
            "pending", "preparing", "ready",
            "completed", "cancelled"
        ]

        if new_status in valid_statuses:
            order.status = new_status
            order.save()

        return redirect("admin_order_detail", order_id=order.id)

    return render(
        request,
        "cafeapp/admin_order_detail.html",
        {"order": order}
    )


# =========================
# ADMIN MENU MANAGEMENT
# =========================

def admin_menu(request):
    menu_items = MenuItem.objects.select_related(
        "category"
    ).order_by("category__name", "name")

    return render(
        request,
        "cafeapp/admin_menu.html",
        {"menu_items": menu_items}
    )


def admin_add_menu(request):
    categories = Category.objects.all().order_by("name")

    if request.method == "POST":
        category_id = request.POST.get("category")

        category = get_object_or_404(Category, id=category_id)

        MenuItem.objects.create(
            category=category,
            name=request.POST.get("name"),
            description=request.POST.get("description"),
            price=request.POST.get("price"),
            image=request.FILES.get("image"),
            is_available=request.POST.get("is_available") == "on",
            is_veg=request.POST.get("food_type", "veg") == "veg",
            is_bestseller=request.POST.get("is_bestseller") == "on",
        )

        return redirect("admin_menu")

    return render(
        request,
        "cafeapp/admin_add_menu.html",
        {"categories": categories}
    )


def admin_edit_menu(request, item_id):
    item = get_object_or_404(MenuItem, id=item_id)
    categories = Category.objects.all().order_by("name")

    if request.method == "POST":
        category_id = request.POST.get("category")
        item.category = get_object_or_404(Category, id=category_id)
        item.name = request.POST.get("name")
        item.description = request.POST.get("description")
        item.price = request.POST.get("price")
        item.is_available = request.POST.get("is_available") == "on"
        item.is_veg = request.POST.get("food_type", "veg") == "veg"
        item.is_bestseller = request.POST.get("is_bestseller") == "on"

        image = request.FILES.get("image")
        if image:
            item.image = image

        item.save()
        return redirect("admin_menu")

    return render(
        request,
        "cafeapp/admin_edit_menu.html",
        {"item": item, "categories": categories}
    )


def admin_delete_menu(request, item_id):
    item = get_object_or_404(MenuItem, id=item_id)

    if request.method == "POST":
        item.delete()
        return redirect("admin_menu")

    return render(
        request,
        "cafeapp/admin_delete_menu.html",
        {"item": item}
    )


# =========================
# ADMIN CATEGORY MANAGEMENT
# =========================

VALID_LAYOUTS = ("auto", "list", "grid", "big")


def _category_extras(request):
    layout = request.POST.get("layout", "auto")

    if layout not in VALID_LAYOUTS:
        layout = "auto"

    try:
        order = int(request.POST.get("order") or 0)
    except (ValueError, TypeError):
        order = 0

    return layout, order


def admin_categories(request):
    categories = Category.objects.all().order_by("name")

    return render(
        request,
        "cafeapp/admin_categories.html",
        {"categories": categories}
    )


def admin_add_category(request):
    if request.method == "POST":
        name = request.POST.get("name", "").strip()
        layout, order = _category_extras(request)

        if name:
            Category.objects.create(
                name=name,
                image=request.FILES.get("image"),
                layout=layout,
                order=order,
            )

        return redirect("admin_categories")

    return render(request, "cafeapp/admin_add_category.html")


def admin_edit_category(request, category_id):
    category = get_object_or_404(Category, id=category_id)

    if request.method == "POST":
        name = request.POST.get("name", "").strip()
        layout, order = _category_extras(request)
        image = request.FILES.get("image")

        if name:
            category.name = name
            category.layout = layout
            category.order = order

            if image:
                category.image = image

            category.save()

        return redirect("admin_categories")

    return render(
        request,
        "cafeapp/admin_edit_category.html",
        {"category": category}
    )


def admin_delete_category(request, category_id):
    category = get_object_or_404(Category, id=category_id)

    if request.method == "POST":
        category.delete()
        return redirect("admin_categories")

    return render(
        request,
        "cafeapp/admin_delete_category.html",
        {"category": category}
    )


# =========================
# ADMIN TABLE MANAGEMENT
# =========================

def admin_tables(request):
    tables = Table.objects.all().order_by("table_number")

    return render(
        request,
        "cafeapp/admin_tables.html",
        {"tables": tables}
    )


def admin_add_table(request):
    if request.method == "POST":
        table_number = request.POST.get("table_number")
        is_active = request.POST.get("is_active") == "on"

        if table_number:
            Table.objects.create(
                table_number=table_number,
                is_active=is_active,
            )

        return redirect("admin_tables")

    return render(request, "cafeapp/admin_add_table.html")


def admin_edit_table(request, table_id):
    table = get_object_or_404(Table, id=table_id)

    if request.method == "POST":
        table_number = request.POST.get("table_number")
        is_active = request.POST.get("is_active") == "on"

        if table_number:
            table.table_number = table_number
            table.is_active = is_active
            table.save()

        return redirect("admin_tables")

    return render(
        request,
        "cafeapp/admin_edit_table.html",
        {"table": table}
    )


# =========================
# QR CODE GENERATION
# =========================

def admin_qr_codes(request):
    tables = Table.objects.all().order_by("table_number")

    return render(
        request,
        "cafeapp/admin_qr_codes.html",
        {"tables": tables}
    )


def admin_generate_qr(request, table_id):
    table = get_object_or_404(Table, id=table_id)

    menu_url = request.build_absolute_uri(
        reverse("menu", args=[table.table_number])
    )

    qr_image = qrcode.make(menu_url)
    buffer = BytesIO()
    qr_image.save(buffer, format="PNG")
    buffer.seek(0)

    return HttpResponse(
        buffer.getvalue(),
        content_type="image/png"
    )


# =========================
# NEW ORDER CHECK
# =========================

def admin_new_orders(request):
    last_order_id = request.GET.get("last_order_id", 0)

    try:
        last_order_id = int(last_order_id)
    except (TypeError, ValueError):
        last_order_id = 0

    new_order = (
        Order.objects
        .select_related("table")
        .filter(id__gt=last_order_id)
        .order_by("id")
        .first()
    )

    if new_order:
        return JsonResponse({
            "new_order": True,
            "order_id": new_order.id,
            "table_number": new_order.table.table_number,
            "total_amount": str(new_order.total_amount),
        })

    return JsonResponse({"new_order": False})


# =========================
# ACCEPT ORDER (from notification popup)
# =========================

@user_passes_test(is_admin_user, login_url="/admin-login/")
@require_POST
def admin_accept_order(request):
    order = get_object_or_404(Order, id=request.POST.get("order_id"))

    if order.status == "pending":
        order.status = "preparing"
        order.save()

    return JsonResponse({
        "success": True,
        "status": order.status,
    })

# =========================
# ADMIN BANNERS
# =========================

@user_passes_test(is_admin_user, login_url="/admin-login/")
def admin_banners(request):
    if request.method == "POST":
        title = request.POST.get("title", "").strip()

        if title:
            try:
                order = int(request.POST.get("order") or 0)
            except (ValueError, TypeError):
                order = 0

            Banner.objects.create(
                title=title,
                subtitle=request.POST.get("subtitle", "").strip(),
                tag=request.POST.get("tag", "").strip(),
                image=request.FILES.get("image"),
                order=order,
                is_active=request.POST.get("is_active") == "on",
            )

        return redirect("admin_banners")

    return render(
        request,
        "cafeapp/admin_banners.html",
        {"banners": Banner.objects.all()}
    )


@user_passes_test(is_admin_user, login_url="/admin-login/")
@require_POST
def admin_banner_toggle(request, banner_id):
    banner = get_object_or_404(Banner, id=banner_id)
    banner.is_active = not banner.is_active
    banner.save()
    return redirect("admin_banners")


@user_passes_test(is_admin_user, login_url="/admin-login/")
@require_POST
def admin_banner_delete(request, banner_id):
    banner = get_object_or_404(Banner, id=banner_id)
    banner.delete()
    return redirect("admin_banners")


def my_orders(request, table_id):
    table = get_object_or_404(
        Table,
        table_number=table_id,
        is_active=True
    )

    order_ids = request.session.get("my_order_ids", [])

    orders = (
        Order.objects
        .filter(
            table=table,
            id__in=order_ids
        )
        .exclude(
            status__in=["completed", "cancelled"]
        )
        .prefetch_related("items__menu_item")
        .order_by("-order_time")
    )

    return render(
        request,
        "cafeapp/my_orders.html",
        {
            "table": table,
            "orders": orders,
        }
    )

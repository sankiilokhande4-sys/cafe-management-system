from io import BytesIO

import qrcode
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import user_passes_test
from django.db import transaction
from django.db.models import Prefetch
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from .models import Table, Category, MenuItem, Order, OrderItem, Banner
from .pricing import build_cart_lines, get_customization_config
from decimal import Decimal, InvalidOperation
from .pricing import build_cart_lines, get_customization_config,active_groups
from .models import (
    Table, Category, MenuItem, Order, OrderItem, Banner,
    CustomizationGroup, CustomizationOption,
)

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

    # Total includes customization extras, same as the cart page.
    _, cart_total = build_cart_lines(
        cart_data,
        request.session.get("cart_options", {}),
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
    table = get_object_or_404(Table, table_number=table_id, is_active=True)

    cart_items, total = build_cart_lines(
        request.session.get("cart", {}),
        request.session.get("cart_options", {}),
    )

    total_qty = sum(line["quantity"] for line in cart_items)

    return render(
        request,
        "cafeapp/cart.html",
        {
            "table": table,
            "cart_items": cart_items,
            "total": total,
            "total_qty": total_qty,
        },
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


@require_POST
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

SPICE_LEVELS = ["Mild", "Medium", "Hot"]
SUGAR_LEVELS = ["No sugar", "Less", "Normal", "Extra"]

@require_POST
def save_customization(request, table_id, item_id):
    table = get_object_or_404(Table, table_number=table_id, is_active=True)
    item = get_object_or_404(MenuItem, id=item_id, is_available=True)

    cart_data = request.session.get("cart", {})
    key = str(item.id)

    if key not in cart_data:
        return redirect("cart", table_id=table.table_number)

    post = request.POST
    notes = post.get("notes", "").strip()[:250]
    groups = active_groups(item)

    if groups:
        # Admin-defined options: save the chosen option ids.
        chosen = []

        for group, options in groups:
            valid = {str(o.id): o for o in options}
            picked = [v for v in post.getlist(f"group_{group.id}") if v in valid]

            if group.choice_type == "single":
                picked = picked[:1]

            # A required group always gets a choice (the default, or the first).
            if not picked and group.is_required:
                fallback = next((o for o in options if o.is_default), options[0])
                picked = [str(fallback.id)]

            chosen.extend(int(v) for v in picked)

        selected = {"options": chosen, "notes": notes}

    else:
        # Old hard-coded options (items with no admin groups yet).
        config = get_customization_config(item)

        def checked(name):
            return post.get(name) in ("on", "yes")

        spice = post.get("spice", "Mild")
        if spice not in SPICE_LEVELS:
            spice = "Mild"

        selected = {"notes": notes}

        if config["type"] == "pizza":
            size = post.get("size", "Regular")
            if size not in config["sizes"]:
                size = "Regular"

            selected["size"] = size
            selected["extra_cheese"] = checked("extra_cheese")
            selected["toppings"] = [
                t.strip()[:50] for t in post.getlist("toppings") if t.strip()
            ]
            selected["spicy"] = spice

        elif config["type"] == "burger":
            selected["extra_cheese"] = checked("extra_cheese")
            selected["spicy"] = spice

        elif config["type"] == "drink":
            size = post.get("size", "Regular")
            if size not in ("Regular", "Large"):
                size = "Regular"

            sugar = post.get("sugar", "Normal")
            if sugar not in SUGAR_LEVELS:
                sugar = "Normal"

            selected["size"] = size
            selected["extra_milk"] = checked("extra_milk")
            selected["sugar"] = sugar

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
    table = get_object_or_404(Table, table_number=table_id, is_active=True)

    payment_method = request.POST.get("payment_method", "cash").lower()
    if payment_method not in ["cash", "upi"]:
        payment_method = "cash"

    lines, total = build_cart_lines(
        request.session.get("cart", {}),
        request.session.get("cart_options", {}),
    )

    if not lines:
        return redirect("cart", table_id=table.table_number)

    with transaction.atomic():
        order = Order.objects.create(
            table=table,
            total_amount=total,
            payment_method=payment_method,
            payment_status="unpaid",
        )

        for line in lines:
            customization = dict(line["selected"])

            # Save a snapshot of option names and prices, so later price
            # changes by the admin never alter old orders.
            if line["option_details"]:
                customization["option_details"] = line["option_details"]

            OrderItem.objects.create(
                order=order,
                menu_item=line["item"],
                quantity=line["quantity"],
                price=line["item"].price,
                customization=customization,
                customization_price=line["extra_price"],
            )

    request.session["cart"] = {}
    request.session["cart_options"] = {}

    order_ids = request.session.get("my_order_ids", [])
    if order.id not in order_ids:
        order_ids.append(order.id)

    request.session["my_order_ids"] = order_ids
    request.session["last_order_id"] = order.id
    request.session.modified = True

    return redirect(
        "order_success",
        table_id=table.table_number,
        order_id=order.id,
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
# ADMIN ITEM CUSTOMIZATIONS
# =========================

def _parse_price(value):
    """Returns a valid non-negative Decimal, or None if the input is bad."""
    try:
        price = Decimal(str(value).strip() or "0")
    except InvalidOperation:
        return None

    if not price.is_finite() or price < 0 or price > Decimal("99999.99"):
        return None

    return price.quantize(Decimal("0.01"))


def _back_to_item(item_id):
    return redirect("admin_item_customizations", item_id=item_id)


@user_passes_test(is_admin_user, login_url="/admin-login/")
def admin_item_customizations(request, item_id):
    item = get_object_or_404(MenuItem, id=item_id)
    groups = item.customization_groups.prefetch_related("options")

    return render(
        request,
        "cafeapp/admin_item_customizations.html",
        {"item": item, "groups": groups},
    )


@user_passes_test(is_admin_user, login_url="/admin-login/")
@require_POST
def admin_add_group(request, item_id):
    item = get_object_or_404(MenuItem, id=item_id)

    name = request.POST.get("name", "").strip()[:100]
    choice_type = request.POST.get("choice_type", "multiple")

    if choice_type not in ("single", "multiple"):
        choice_type = "multiple"

    if name:
        last = item.customization_groups.order_by("-order").first()

        CustomizationGroup.objects.create(
            menu_item=item,
            name=name,
            choice_type=choice_type,
            is_required=request.POST.get("is_required") == "on",
            order=(last.order + 1) if last else 0,
        )

    return _back_to_item(item.id)


@user_passes_test(is_admin_user, login_url="/admin-login/")
@require_POST
def admin_toggle_group(request, group_id):
    group = get_object_or_404(CustomizationGroup, id=group_id)
    group.is_active = not group.is_active
    group.save(update_fields=["is_active"])
    return _back_to_item(group.menu_item_id)


@user_passes_test(is_admin_user, login_url="/admin-login/")
@require_POST
def admin_delete_group(request, group_id):
    group = get_object_or_404(CustomizationGroup, id=group_id)
    item_id = group.menu_item_id
    group.delete()
    return _back_to_item(item_id)


@user_passes_test(is_admin_user, login_url="/admin-login/")
@require_POST
def admin_add_option(request, group_id):
    group = get_object_or_404(CustomizationGroup, id=group_id)

    name = request.POST.get("name", "").strip()[:100]
    price = _parse_price(request.POST.get("extra_price"))
    is_default = request.POST.get("is_default") == "on"

    if name and price is not None:
        # A "choose one" group can only have one default option.
        if is_default and group.choice_type == "single":
            group.options.update(is_default=False)

        last = group.options.order_by("-order").first()

        CustomizationOption.objects.create(
            group=group,
            name=name,
            extra_price=price,
            is_default=is_default,
            order=(last.order + 1) if last else 0,
        )

    return _back_to_item(group.menu_item_id)


@user_passes_test(is_admin_user, login_url="/admin-login/")
@require_POST
def admin_update_option(request, option_id):
    option = get_object_or_404(
        CustomizationOption.objects.select_related("group"),
        id=option_id,
    )

    name = request.POST.get("name", "").strip()[:100]
    price = _parse_price(request.POST.get("extra_price"))
    is_default = request.POST.get("is_default") == "on"

    if name and price is not None:
        if is_default and option.group.choice_type == "single":
            option.group.options.exclude(id=option.id).update(is_default=False)

        option.name = name
        option.extra_price = price
        option.is_default = is_default
        option.save()

    return _back_to_item(option.group.menu_item_id)


@user_passes_test(is_admin_user, login_url="/admin-login/")
@require_POST
def admin_toggle_option(request, option_id):
    option = get_object_or_404(
        CustomizationOption.objects.select_related("group"),
        id=option_id,
    )
    option.is_active = not option.is_active
    option.save(update_fields=["is_active"])
    return _back_to_item(option.group.menu_item_id)


@user_passes_test(is_admin_user, login_url="/admin-login/")
@require_POST
def admin_delete_option(request, option_id):
    option = get_object_or_404(
        CustomizationOption.objects.select_related("group"),
        id=option_id,
    )
    item_id = option.group.menu_item_id
    option.delete()
    return _back_to_item(item_id)



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


# =========================
# CUSTOMER: MY ORDERS
# =========================

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
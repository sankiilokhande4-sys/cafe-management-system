from decimal import Decimal
from io import BytesIO
from django.http import JsonResponse
import qrcode
from django.contrib.auth import authenticate, login, logout
from django.shortcuts import get_object_or_404, render, redirect
from django.views.decorators.http import require_POST
from django.http import HttpResponse
from django.urls import reverse
from django.contrib.auth.decorators import user_passes_test
from .models import Table, Category, MenuItem, Order
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
            {
                "error": "Invalid username or password."
            }
        )

    return render(
        request,
        "cafeapp/admin_login.html"
    )


def admin_logout(request):

    logout(request)

    return redirect("admin_login")
def home(request):
    return render(request, "cafeapp/home.html")


def menu(request, table_id):
    table = get_object_or_404(
        Table,
        table_number=table_id,
        is_active=True
    )

    categories = Category.objects.prefetch_related(
        "menu_items"
    ).all()

    return render(
        request,
        "cafeapp/menu.html",
        {
            "table": table,
            "categories": categories,
        }
    )


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

    cart = request.session.get("cart", {})

    item_key = str(item.id)

    cart[item_key] = cart.get(item_key, 0) + 1

    request.session["cart"] = cart
    request.session["cart_table"] = table.table_number

    return redirect(
        "cart",
        table_id=table.table_number
    )


def cart(request, table_id):
    table = get_object_or_404(
        Table,
        table_number=table_id,
        is_active=True
    )

    cart = request.session.get("cart", {})

    menu_items = MenuItem.objects.filter(
        id__in=cart.keys(),
        is_available=True
    )

    cart_items = []
    total = Decimal("0.00")

    for item in menu_items:

        quantity = int(
            cart.get(str(item.id), 0)
        )

        subtotal = item.price * quantity

        total += subtotal

        cart_items.append(
            {
                "item": item,
                "quantity": quantity,
                "subtotal": subtotal,
            }
        )

    return render(
        request,
        "cafeapp/cart.html",
        {
            "table": table,
            "cart_items": cart_items,
            "total": total,
        }
    )


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

    cart = request.session.get("cart", {})

    item_key = str(item.id)

    if item_key in cart:
        cart[item_key] += 1
    else:
        cart[item_key] = 1

    request.session["cart"] = cart

    return redirect(
        "cart",
        table_id=table.table_number
    )


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

    cart = request.session.get("cart", {})

    item_key = str(item.id)

    if item_key in cart:

        cart[item_key] -= 1

        if cart[item_key] <= 0:
            del cart[item_key]

    request.session["cart"] = cart

    return redirect(
        "cart",
        table_id=table.table_number
    )


@require_POST
def remove_from_cart(request, table_id, item_id):
    table = get_object_or_404(
        Table,
        table_number=table_id,
        is_active=True
    )

    cart = request.session.get("cart", {})

    item_key = str(item_id)

    if item_key in cart:
        del cart[item_key]

    request.session["cart"] = cart

    return redirect(
        "cart",
        table_id=table.table_number
    )
@require_POST
def place_order(request, table_id):
    table = get_object_or_404(
        Table,
        table_number=table_id,
        is_active=True
    )

    cart = request.session.get("cart", {})

    if not cart:
        return redirect(
            "cart",
            table_id=table.table_number
        )

    menu_items = MenuItem.objects.filter(
        id__in=cart.keys(),
        is_available=True
    )

    if not menu_items.exists():
        return redirect(
            "cart",
            table_id=table.table_number
        )

    from .models import Order, OrderItem

    order = Order.objects.create(
        table=table,
        total_amount=Decimal("0.00")
    )

    total = Decimal("0.00")

    for item in menu_items:

        quantity = int(
            cart.get(str(item.id), 0)
        )

        if quantity <= 0:
            continue

        subtotal = item.price * quantity

        OrderItem.objects.create(
            order=order,
            menu_item=item,
            quantity=quantity,
            price=item.price
        )

        total += subtotal

    order.total_amount = total
    order.save()

    # Clear cart after successful order
    request.session["cart"] = {}

    # Save last order ID in session
    request.session["last_order_id"] = order.id

    return redirect(
        "order_success",
        table_id=table.table_number,
        order_id=order.id
    )
def order_success(request, table_id, order_id):
    table = get_object_or_404(
        Table,
        table_number=table_id,
        is_active=True
    )

    from .models import Order

    order = get_object_or_404(
        Order,
        id=order_id,
        table=table
    )

    return render(
        request,
        "cafeapp/order_success.html",
        {
            "table": table,
            "order": order,
        }
    )
def order_status(request, table_id, order_id):
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
        "cafeapp/order_status.html",
        {
            "table": table,
            "order": order,
        }
    )
def is_admin_user(user):
    return user.is_authenticated and user.is_staff
@user_passes_test(is_admin_user, login_url="/admin-login/")
def admin_dashboard(request):
    from .models import Order

    pending_orders = Order.objects.filter(
        status="pending"
    ).count()

    preparing_orders = Order.objects.filter(
        status="preparing"
    ).count()

    ready_orders = Order.objects.filter(
        status="ready"
    ).count()

    completed_orders = Order.objects.filter(
        status="completed"
    ).count()

    recent_orders = Order.objects.select_related(
        "table"
    ).order_by(
        "-order_time"
    )[:10]

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
    from .models import Order

    if request.method == "POST":

        order_id = request.POST.get("order_id")
        new_status = request.POST.get("status")

        valid_statuses = [
            "pending",
            "preparing",
            "ready",
            "completed",
            "cancelled",
        ]

        if new_status in valid_statuses:

            order = get_object_or_404(
                Order,
                id=order_id
            )

            order.status = new_status
            order.save()

        return redirect("admin_orders")


    status_filter = request.GET.get("status")


    orders = Order.objects.select_related(
        "table"
    ).order_by("-order_time")


    valid_statuses = [
        "pending",
        "preparing",
        "ready",
        "completed",
        "cancelled",
    ]


    if status_filter in valid_statuses:

        orders = orders.filter(
            status=status_filter
        )


    return render(
        request,
        "cafeapp/admin_orders.html",
        {
            "orders": orders,
            "status_filter": status_filter,
        }
    )
def admin_order_detail(request, order_id):
    from .models import Order

    order = get_object_or_404(
        Order,
        id=order_id
    )

    if request.method == "POST":

        new_status = request.POST.get("status")

        valid_statuses = [
            "pending",
            "preparing",
            "ready",
            "completed",
            "cancelled",
        ]

        if new_status in valid_statuses:
            order.status = new_status
            order.save()

        return redirect(
            "admin_order_detail",
            order_id=order.id
        )

    return render(
        request,
        "cafeapp/admin_order_detail.html",
        {
            "order": order,
        }
    )
def admin_menu(request):
    from .models import MenuItem

    menu_items = MenuItem.objects.select_related(
        "category"
    ).order_by(
        "category__name",
        "name"
    )

    return render(
        request,
        "cafeapp/admin_menu.html",
        {
            "menu_items": menu_items,
        }
    )
def admin_add_menu(request):
    from .models import Category, MenuItem

    categories = Category.objects.all().order_by("name")

    if request.method == "POST":
        category_id = request.POST.get("category")
        name = request.POST.get("name")
        description = request.POST.get("description")
        price = request.POST.get("price")
        image = request.FILES.get("image")
        is_available = request.POST.get("is_available") == "on"

        category = get_object_or_404(
            Category,
            id=category_id
        )

        MenuItem.objects.create(
            category=category,
            name=name,
            description=description,
            price=price,
            image=image,
            is_available=is_available,
        )

        return redirect("admin_menu")

    return render(
        request,
        "cafeapp/admin_add_menu.html",
        {
            "categories": categories,
        }
    )
def admin_categories(request):
    from .models import Category

    categories = Category.objects.all().order_by("name")

    return render(
        request,
        "cafeapp/admin_categories.html",
        {
            "categories": categories,
        }
    )


def admin_add_category(request):
    from .models import Category

    if request.method == "POST":
        name = request.POST.get("name", "").strip()

        if name:
            Category.objects.create(
                name=name
            )

        return redirect("admin_categories")

    return render(
        request,
        "cafeapp/admin_add_category.html"
    )
def admin_edit_menu(request, item_id):
    from .models import Category, MenuItem

    item = get_object_or_404(
        MenuItem,
        id=item_id
    )

    categories = Category.objects.all().order_by("name")

    if request.method == "POST":
        category_id = request.POST.get("category")
        name = request.POST.get("name")
        description = request.POST.get("description")
        price = request.POST.get("price")
        image = request.FILES.get("image")
        is_available = request.POST.get("is_available") == "on"

        category = get_object_or_404(
            Category,
            id=category_id
        )

        item.category = category
        item.name = name
        item.description = description
        item.price = price
        item.is_available = is_available

        if image:
            item.image = image

        item.save()

        return redirect("admin_menu")

    return render(
        request,
        "cafeapp/admin_edit_menu.html",
        {
            "item": item,
            "categories": categories,
        }
    )


def admin_delete_menu(request, item_id):
    from .models import MenuItem

    item = get_object_or_404(
        MenuItem,
        id=item_id
    )

    if request.method == "POST":
        item.delete()
        return redirect("admin_menu")

    return render(
        request,
        "cafeapp/admin_delete_menu.html",
        {
            "item": item,
        }
    )
def admin_edit_category(request, category_id):
    from .models import Category

    category = get_object_or_404(
        Category,
        id=category_id
    )

    if request.method == "POST":
        name = request.POST.get("name", "").strip()

        if name:
            category.name = name
            category.save()

        return redirect("admin_categories")

    return render(
        request,
        "cafeapp/admin_edit_category.html",
        {
            "category": category,
        }
    )


def admin_delete_category(request, category_id):
    from .models import Category

    category = get_object_or_404(
        Category,
        id=category_id
    )

    if request.method == "POST":
        category.delete()
        return redirect("admin_categories")

    return render(
        request,
        "cafeapp/admin_delete_category.html",
        {
            "category": category,
        }
    )
def admin_tables(request):
    from .models import Table

    tables = Table.objects.all().order_by("table_number")

    return render(
        request,
        "cafeapp/admin_tables.html",
        {
            "tables": tables,
        }
    )


def admin_add_table(request):
    from .models import Table

    if request.method == "POST":
        table_number = request.POST.get("table_number")
        is_active = request.POST.get("is_active") == "on"

        if table_number:
            Table.objects.create(
                table_number=table_number,
                is_active=is_active,
            )

        return redirect("admin_tables")

    return render(
        request,
        "cafeapp/admin_add_table.html"
    )
def admin_edit_table(request, table_id):
    from .models import Table

    table = get_object_or_404(
        Table,
        id=table_id
    )

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
        {
            "table": table,
        }
    )
def admin_qr_codes(request):
    from .models import Table

    tables = Table.objects.all().order_by("table_number")

    return render(
        request,
        "cafeapp/admin_qr_codes.html",
        {
            "tables": tables,
        }
    )


def admin_generate_qr(request, table_id):
    from .models import Table

    table = get_object_or_404(
        Table,
        id=table_id
    )

    menu_url = request.build_absolute_uri(
        reverse(
            "menu",
            args=[table.table_number]
        )
    )

    qr_image = qrcode.make(menu_url)

    buffer = BytesIO()

    qr_image.save(
        buffer,
        format="PNG"
    )

    buffer.seek(0)

    response = HttpResponse(
        buffer.getvalue(),
        content_type="image/png"
    )

    return response
def admin_new_orders(request):
    from .models import Order

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

    return JsonResponse({
        "new_order": False
    })
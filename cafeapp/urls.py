from django.urls import path

from . import views


urlpatterns = [
    path(
    "admin-login/",
    views.admin_login,
    name="admin_login"
),

path(
    "admin-logout/",
    views.admin_logout,
    name="admin_logout"
),
    path(
        "",
        views.home,
        name="home"
    ),

    path(
        "menu/<int:table_id>/",
        views.menu,
        name="menu"
    ),

    path(
        "menu/<int:table_id>/add/<int:item_id>/",
        views.add_to_cart,
        name="add_to_cart"
    ),

    path(
        "cart/<int:table_id>/",
        views.cart,
        name="cart"
    ),

    path(
        "cart/<int:table_id>/increase/<int:item_id>/",
        views.increase_quantity,
        name="increase_quantity"
    ),

    path(
        "cart/<int:table_id>/decrease/<int:item_id>/",
        views.decrease_quantity,
        name="decrease_quantity"
    ),

    path(
        "cart/<int:table_id>/remove/<int:item_id>/",
        views.remove_from_cart,
        name="remove_from_cart"
    ),
    path(
    "cart/<int:table_id>/place-order/",
    views.place_order,
    name="place_order"
    ),

path(
    "order/<int:table_id>/<int:order_id>/success/",
    views.order_success,
    name="order_success"
),
path(
    "order/<int:table_id>/<int:order_id>/status/",
    views.order_status,
    name="order_status"
),
path(
    "admin-dashboard/",
    views.admin_dashboard,
    name="admin_dashboard"
),
path(
    "admin-orders/",
    views.admin_orders,
    name="admin_orders"
),
path(
    "admin-orders/<int:order_id>/",
    views.admin_order_detail,
    name="admin_order_detail"
),
path(
    "admin-menu/",
    views.admin_menu,
    name="admin_menu"
),
path(
    "admin-menu/add/",
    views.admin_add_menu,
    name="admin_add_menu"
),
path(
    "admin-categories/",
    views.admin_categories,
    name="admin_categories"
),

path(
    "admin-categories/add/",
    views.admin_add_category,
    name="admin_add_category"
),
path(
    "admin-menu/<int:item_id>/edit/",
    views.admin_edit_menu,
    name="admin_edit_menu"
),

path(
    "admin-menu/<int:item_id>/delete/",
    views.admin_delete_menu,
    name="admin_delete_menu"
),
path(
    "admin-categories/<int:category_id>/edit/",
    views.admin_edit_category,
    name="admin_edit_category"
),

path(
    "admin-categories/<int:category_id>/delete/",
    views.admin_delete_category,
    name="admin_delete_category"
),
path(
    "admin-tables/",
    views.admin_tables,
    name="admin_tables"
),

path(
    "admin-tables/add/",
    views.admin_add_table,
    name="admin_add_table"
),

path(
    "admin-tables/<int:table_id>/edit/",
    views.admin_edit_table,
    name="admin_edit_table"
),

path(
    "admin-qr/",
    views.admin_qr_codes,
    name="admin_qr_codes"
),

path(
    "admin-qr/<int:table_id>/",
    views.admin_generate_qr,
    name="admin_generate_qr"
),
path(
    "admin-new-orders/",
    views.admin_new_orders,
    name="admin_new_orders"
),
]
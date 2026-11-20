
from datetime import date, datetime, time, timedelta
from decimal import Decimal

from django.db.models import (
    Count,
    Sum,
    F,
    ExpressionWrapper,
    DecimalField,
)
from django.utils import timezone

from .models import Order, OrderItem


# ==========================================
# ANALYTICS DATE RANGE
# ==========================================

def get_analytics_date_range(period="today", start_date=None, end_date=None):
    """
    Returns timezone-aware start and end datetimes.

    Supported periods:
        today
        7days
        30days
        month
        custom

    The end datetime is exclusive.
    """

    today = timezone.localdate()
    current_timezone = timezone.get_current_timezone()

    if period == "7days":
        first_day = today - timedelta(days=6)
        last_day = today

    elif period == "30days":
        first_day = today - timedelta(days=29)
        last_day = today

    elif period == "month":
        first_day = today.replace(day=1)
        last_day = today

    elif period == "custom":
        try:
            first_day = date.fromisoformat(start_date)
            last_day = date.fromisoformat(end_date)

            if first_day > last_day:
                raise ValueError("Start date cannot be after end date.")

        except (TypeError, ValueError):
            first_day = today
            last_day = today

    else:
        first_day = today
        last_day = today

    start_datetime = timezone.make_aware(
        datetime.combine(first_day, time.min),
        current_timezone,
    )

    end_datetime = timezone.make_aware(
        datetime.combine(last_day + timedelta(days=1), time.min),
        current_timezone,
    )

    return start_datetime, end_datetime


# ==========================================
# COMMON ORDER QUERY
# ==========================================

def get_orders_for_period(start_datetime, end_datetime):
    """
    Returns orders created within the selected date range.
    """

    return Order.objects.filter(
        order_time__gte=start_datetime,
        order_time__lt=end_datetime,
    )


# ==========================================
# SALES SUMMARY
# ==========================================

def get_sales_summary(start_datetime, end_datetime):
    """
    Calculates sales, collections and order statistics.
    """

    period_orders = get_orders_for_period(
        start_datetime,
        end_datetime,
    )

    # Cancelled orders are not considered valid sales.
    valid_orders = period_orders.exclude(status="cancelled")

    # Revenue is calculated only from completed orders.
    completed_orders = valid_orders.filter(status="completed")

    # Only paid, non-cancelled orders count as collections.
    paid_orders = valid_orders.filter(payment_status="paid")

    completed_stats = completed_orders.aggregate(
        total_revenue=Sum("total_amount"),
        total_orders=Count("id"),
    )

    paid_stats = paid_orders.aggregate(
        total_collected=Sum("total_amount"),
    )

    cash_stats = paid_orders.filter(
        payment_method="cash"
    ).aggregate(
        cash_collected=Sum("total_amount"),
    )

    upi_stats = paid_orders.filter(
        payment_method="upi"
    ).aggregate(
        upi_collected=Sum("total_amount"),
    )

    cancelled_orders = period_orders.filter(
        status="cancelled"
    ).count()

    total_orders = valid_orders.count()

    total_revenue = (
        completed_stats["total_revenue"] or Decimal("0.00")
    )

    completed_order_count = completed_stats["total_orders"] or 0

    total_collected = (
        paid_stats["total_collected"] or Decimal("0.00")
    )

    cash_collected = (
        cash_stats["cash_collected"] or Decimal("0.00")
    )

    upi_collected = (
        upi_stats["upi_collected"] or Decimal("0.00")
    )

    # Average value of completed orders.
    if completed_order_count:
        average_order_value = (
            total_revenue / completed_order_count
        )
    else:
        average_order_value = Decimal("0.00")

    # Count quantity sold only in completed orders.
    items_sold = OrderItem.objects.filter(
        order__in=completed_orders
    ).aggregate(
        total_quantity=Sum("quantity")
    )["total_quantity"] or 0

    return {
        "total_revenue": total_revenue,
        "total_collected": total_collected,
        "cash_collected": cash_collected,
        "upi_collected": upi_collected,
        "total_orders": total_orders,
        "completed_orders": completed_order_count,
        "cancelled_orders": cancelled_orders,
        "items_sold": items_sold,
        "average_order_value": average_order_value,
    }


# ==========================================
# BEST SELLING PRODUCTS
# ==========================================

def get_best_selling_products(
    start_datetime,
    end_datetime,
    limit=10,
):
    """
    Returns the best-selling products by quantity.

    Only completed orders are included.
    """

    completed_orders = get_orders_for_period(
        start_datetime,
        end_datetime,
    ).filter(status="completed")

    item_revenue_expression = ExpressionWrapper(
        F("quantity") * (
            F("price") + F("customization_price")
        ),
        output_field=DecimalField(
            max_digits=14,
            decimal_places=2,
        ),
    )

    products = (
        OrderItem.objects
        .filter(order__in=completed_orders)
        .values(
            "menu_item_id",
            "menu_item__name",
        )
        .annotate(
            quantity_sold=Sum("quantity"),
            product_revenue=Sum(item_revenue_expression),
        )
        .order_by("-quantity_sold", "-product_revenue")[:limit]
    )

    return products


# ==========================================
# DAILY SALES
# ==========================================

def get_daily_sales(start_datetime, end_datetime):
    """
    Returns daily revenue and completed-order counts.

    The results are grouped by date.
    """

    completed_orders = get_orders_for_period(
        start_datetime,
        end_datetime,
    ).filter(status="completed")

    daily_data = (
        completed_orders
        .values("order_time__date")
        .annotate(
            daily_revenue=Sum("total_amount"),
            daily_orders=Count("id"),
        )
        .order_by("order_time__date")
    )

    return daily_data

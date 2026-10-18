from .models import Order


def latest_order(request):
    user = getattr(request, "user", None)

    if user and user.is_authenticated and user.is_staff:
        last_id = (
            Order.objects
            .order_by("-id")
            .values_list("id", flat=True)
            .first()
        )
        return {"latest_order_id": last_id or 0}

    return {}
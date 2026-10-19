from decimal import Decimal

from .models import MenuItem

ZERO = Decimal("0.00")


# =========================
# LEGACY HARD-CODED RULES
# (used only for items that have no admin-defined options)
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
        return {"type": "burger", "cheese_price": Decimal("25.00")}

    if any(w in name for w in ["coffee", "tea", "chai", "latte", "cappuccino"]):
        return {
            "type": "drink",
            "large_price": Decimal("30.00"),
            "extra_milk_price": Decimal("15.00"),
        }

    return {"type": "other"}


def legacy_extra(config, selected):
    extra = ZERO

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

    return extra


# =========================
# ADMIN-DEFINED OPTIONS
# =========================

def active_groups(item):
    """
    Returns [(group, [active options])] for the item's active groups
    that have at least one active option.
    """
    result = []

    for group in item.customization_groups.all():
        if not group.is_active:
            continue

        options = [o for o in group.options.all() if o.is_active]

        if options:
            result.append((group, options))

    return result


def selected_option_ids(groups, selected):
    """
    The option ids the customer chose. If they have not saved anything
    yet, the admin's default options are used.
    """
    if "options" in selected:
        ids = set()
        for value in selected["options"]:
            try:
                ids.add(int(value))
            except (TypeError, ValueError):
                continue
        return ids

    return {
        option.id
        for _, options in groups
        for option in options
        if option.is_default
    }


def option_extra(groups, chosen_ids):
    """
    Price of the chosen options. Only options that belong to this item's
    active groups can be charged, so a tampered form cannot add others.
    """
    extra = ZERO
    details = []

    for group, options in groups:
        for option in options:
            if option.id in chosen_ids:
                extra += option.extra_price
                details.append({
                    "group": group.name,
                    "name": option.name,
                    "price": str(option.extra_price),
                })

    return extra, details


def groups_for_template(groups, chosen_ids):
    return [
        {
            "id": group.id,
            "name": group.name,
            "single": group.choice_type == "single",
            "required": group.is_required,
            "options": [
                {
                    "id": option.id,
                    "name": option.name,
                    "price": option.extra_price,
                    "checked": option.id in chosen_ids,
                }
                for option in options
            ],
        }
        for group, options in groups
    ]


# =========================
# CART LINES (single source of truth for prices)
# =========================

def build_cart_lines(cart_data, saved_options):
    """Returns (lines, total). Used by the cart, menu bar and place_order."""
    if not cart_data:
        return [], ZERO

    menu_items = (
        MenuItem.objects
        .filter(id__in=cart_data.keys(), is_available=True)
        .select_related("category")
        .prefetch_related("customization_groups__options")
    )

    lines = []
    total = ZERO

    for item in menu_items:
        key = str(item.id)

        try:
            quantity = int(cart_data.get(key, 0))
        except (TypeError, ValueError):
            quantity = 0

        if quantity <= 0:
            continue

        selected = saved_options.get(key, {})
        config = get_customization_config(item)
        groups = active_groups(item)

        if groups:
            chosen_ids = selected_option_ids(groups, selected)
            extra, option_details = option_extra(groups, chosen_ids)
            group_view = groups_for_template(groups, chosen_ids)
        else:
            extra = legacy_extra(config, selected)
            option_details = []
            group_view = []

        unit_price = item.price + extra
        subtotal = unit_price * quantity
        total += subtotal

        lines.append({
            "item": item,
            "quantity": quantity,
            "unit_price": unit_price,
            "extra_price": extra,
            "subtotal": subtotal,
            "config": config,
            "selected": selected,
            "option_details": option_details,
            "groups": group_view,
        })

    return lines, total
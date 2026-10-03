#!/usr/bin/env bash
set -o errexit

pip install -r requirements.txt

python manage.py collectstatic --no-input

python manage.py migrate
python manage.py shell <<'PY'
from cafeapp.models import Table

for number in range(1, 5):
    Table.objects.get_or_create(
        table_number=number,
        defaults={"is_active": True}
    )

print("Tables 1-4 checked/created successfully.")
PY
python manage.py shell <<'PY'
import os
from django.contrib.auth import get_user_model

User = get_user_model()

username = os.environ.get("ADMIN_USERNAME")
password = os.environ.get("ADMIN_PASSWORD")

if username and password:
    user, created = User.objects.get_or_create(
        username=username
    )

    user.set_password(password)
    user.is_staff = True
    user.is_superuser = True
    user.is_active = True
    user.save()

    print(f"Admin user '{username}' checked/created successfully.")
else:
    print("ADMIN_USERNAME or ADMIN_PASSWORD is not set.")
PY
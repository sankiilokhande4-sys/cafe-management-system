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
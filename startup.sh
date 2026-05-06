#!/bin/bash

cd /home/site/wwwroot

python -m pip install --upgrade pip
python -m pip install -r requirements.txt

cd /home/site/wwwroot/src

python manage.py collectstatic --noinput || echo "WARNING: collectstatic failed"
python manage.py migrate --noinput || echo "WARNING: migrate failed - check MySQL connection"

exec gunicorn --bind=0.0.0.0:8000 --timeout=600 --workers=2 cblog.wsgi:application

#!/bin/bash

cd /home/site/wwwroot

python -m pip install -r requirements.txt

cd /home/site/wwwroot/src

python manage.py collectstatic --noinput || echo "WARNING: collectstatic failed"

exec gunicorn --bind=0.0.0.0:8000 --timeout=600 --workers=2 cblog.wsgi:application

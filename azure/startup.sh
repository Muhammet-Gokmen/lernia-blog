#!/bin/bash
# Azure App Service startup script
# Equivalent of AWS EC2 userdata.sh

pip install -r /home/site/wwwroot/requirements.txt

cd /home/site/wwwroot/src

python manage.py collectstatic --noinput
python manage.py makemigrations
python manage.py migrate

gunicorn --bind=0.0.0.0:8000 --timeout=600 --workers=2 cblog.wsgi:application

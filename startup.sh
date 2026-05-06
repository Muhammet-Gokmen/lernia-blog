#!/bin/bash

source /home/site/wwwroot/antenv/bin/activate

cd /home/site/wwwroot/src

python manage.py collectstatic --noinput || echo "WARNING: collectstatic failed"

exec gunicorn --bind=0.0.0.0:8000 --timeout=600 --workers=2 --chdir /home/site/wwwroot/src cblog.wsgi:application

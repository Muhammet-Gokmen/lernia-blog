#!/bin/bash

# Activate virtual environment created by Oryx during build
if [ -d /home/site/wwwroot/antenv ]; then
    source /home/site/wwwroot/antenv/bin/activate
fi

cd /home/site/wwwroot/src

python manage.py collectstatic --noinput || echo "WARNING: collectstatic failed"

exec gunicorn --bind=0.0.0.0:8000 --timeout=600 --workers=2 cblog.wsgi:application

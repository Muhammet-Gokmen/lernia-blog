#!/bin/bash

/opt/python/3.11.14/bin/pip install -r /home/site/wwwroot/requirements.txt

cd /home/site/wwwroot/src

/opt/python/3.11.14/bin/python manage.py collectstatic --noinput || echo "WARNING: collectstatic failed"

exec /opt/python/3.11.14/bin/gunicorn --bind=0.0.0.0:8000 --timeout=600 --workers=2 --chdir /home/site/wwwroot/src cblog.wsgi:application

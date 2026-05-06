#!/bin/bash

VENV="/home/site/wwwroot/venv"

if [ ! -d "$VENV" ]; then
    python -m venv $VENV
    $VENV/bin/pip install -r /home/site/wwwroot/requirements.txt
else
    $VENV/bin/pip install -q -r /home/site/wwwroot/requirements.txt
fi

source $VENV/bin/activate

cd /home/site/wwwroot/src

python manage.py collectstatic --noinput || echo "WARNING: collectstatic failed"

exec gunicorn --bind=0.0.0.0:8000 --timeout=600 --workers=2 --chdir /home/site/wwwroot/src cblog.wsgi:application

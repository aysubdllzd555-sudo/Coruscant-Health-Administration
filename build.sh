#!/usr/bin/env bash
# Render build step: install, collect static files, migrate the database, load catalogue.
set -o errexit
pip install -r requirements.txt
python manage.py collectstatic --no-input
python manage.py migrate --no-input
python manage.py seed_cha ${SEED_DEMO:+--demo}

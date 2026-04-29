#!/bin/bash

# Exit on error
set -e

echo "Running migrations..."
python manage.py migrate --noinput

echo "Seeding data..."
# Use the custom seed command we built
python manage.py seed

echo "Starting Gunicorn..."
gunicorn playto.wsgi --bind 0.0.0.0:8000

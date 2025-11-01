#!/usr/bin/env bash
# Exit on error
set -o errexit

# Run database migrations
python manage.py migrate

# Create a superuser from environment variables if it doesn't exist
python manage.py create_initial_superuser

# Start the bot in the background
echo "Starting Bot in background..."
python bot/bot.py &

# Start the Gunicorn web server in the foreground
echo "Starting Gunicorn..."
gunicorn backend.wsgi:application
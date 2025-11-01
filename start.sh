#!/usr/bin/env bash
# Exit on error
set -o errexit

# Start the bot in the background
echo "Starting Bot in background..."
python bot/bot.py &

# Start the Gunicorn web server in the foreground
echo "Starting Gunicorn..."
gunicorn backend.wsgi:application

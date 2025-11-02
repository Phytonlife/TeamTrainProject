#!/usr/bin/env bash
# Exit on error
set -o errexit

# Run database migrations
python manage.py migrate

# Create a superuser from environment variables if it doesn't exist
python manage.py create_initial_superuser

# Start the bot in the background
echo "--- Starting Bot in background ---"
python bot/bot.py &
BOT_PID=$!
echo "Bot started with PID: $BOT_PID"

# Give the bot a moment to start up and potentially fail
sleep 5

# Check if the bot process is still running
if ! ps -p $BOT_PID > /dev/null; then
  echo "!!! CRITICAL: BOT PROCESS FAILED TO START OR CRASHED. !!!"
  # The script will exit here if the bot crashes because of `set -o errexit` and a failed `ps` command, 
  # but we add an explicit message for clarity.
  exit 1
fi
echo "Bot process is running."

# Start the Gunicorn web server in the foreground
echo "--- Starting Gunicorn ---"
gunicorn backend.wsgi:application

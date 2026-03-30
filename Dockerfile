#!/usr/bin/env bash
set -e

# Default config path
CONFIG_FILE="/data/options.json"
if [ ! -f "$CONFIG_FILE" ]; then
    CONFIG_FILE="/app/config.json"
fi

echo "Starting AI Buffer Server with config: $CONFIG_FILE"
exec uvicorn server:app \
    --host 0.0.0.0 \
    --port 8000 \
    --log-level info
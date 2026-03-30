#!/usr/bin/with-contenv bashio
set -e

# Use bashio to log in the HA UI
bashio::log.info "Starting Ollama Buffer Server..."

# Check if options exist, otherwise use defaults
if bashio::config.has_value 'log_level'; then
    LOG_LEVEL=$(bashio::config 'log_level')
else
    LOG_LEVEL="info"
fi

# Run the server
# 'exec': uvicorn becomes PID 1 and receives shutdown signals
exec uvicorn server:app \
    --host 0.0.0.0 \
    --port 8000 \
    --log-level "${LOG_LEVEL,,}"
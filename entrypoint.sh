#!/bin/sh
set -e

echo "=== Podcast Feed Generator ==="
echo "Input directory: ${INPUT_DIR:-/input}"
echo "Output directory: ${OUTPUT_DIR:-/output}"
echo "Base URL: ${BASE_URL:-http://localhost}"
echo "Regeneration interval: ${REGEN_INTERVAL:-0} seconds (0 = run once)"
echo ""

# Function to run the generator
run_generator() {
    echo "Running generator at $(date)..."
    python3 /app/generator.py
    echo ""
}

# Run generator once on startup
run_generator

# Start Caddy in the background
echo "Starting Caddy server..."
caddy run --config /etc/caddy/Caddyfile --adapter caddyfile &
CADDY_PID=$!

# If REGEN_INTERVAL is set and > 0, run generator periodically
REGEN_INTERVAL=${REGEN_INTERVAL:-0}
if [ "$REGEN_INTERVAL" -gt 0 ]; then
    echo "Starting periodic regeneration (every ${REGEN_INTERVAL} seconds)..."
    while true; do
        sleep "$REGEN_INTERVAL"
        run_generator
    done &
fi

# Wait for Caddy to exit
wait $CADDY_PID

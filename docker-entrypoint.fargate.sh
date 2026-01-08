#!/usr/bin/env bash
set -e

TARGET=/app/alembic/versions        # directory Alembic writes into
APP_USER=seluser                    # runtime UID created by Selenium image

# ── 0) If we're running as root, fix permissions on bind-mounted folder ──────
if [ "$(id -u)" = "0" ]; then
  if [ "$(stat -c '%U' "$TARGET" 2>/dev/null || echo root)" != "$APP_USER" ]; then
    echo "🛠  Adjusting ownership of $TARGET → $APP_USER"
    chown -R "$APP_USER":"$APP_USER" "$TARGET" || true
  fi
fi

# ── 1) Launch Selenium Grid in background (similar to regular Docker) ───────
# Environment variables are now set in docker-compose.fargate.yaml

# Set host explicitly for Selenium Grid
export SE_HOST=0.0.0.0

# Fix for detect-drivers option
# Create a wrapper script to modify the start-selenium-standalone.sh script
cat > /tmp/fix-selenium.sh << 'EOF'
#!/bin/bash
# Find and replace the --detect-drivers false option in the command line
sed -i 's/--detect-drivers false//' /opt/bin/start-selenium-standalone.sh
EOF

# Make the script executable and run it
chmod +x /tmp/fix-selenium.sh
/tmp/fix-selenium.sh

# Start Selenium Grid
/opt/bin/entry_point.sh &
SEL_PID=$!

echo "Waiting for Selenium Grid to be ready …"
# Use same polling approach as regular Docker
until curl -s http://localhost:4444/status | grep -q '"ready":[[:space:]]*true'; do
  sleep 1
done
echo "✅  Selenium Grid is up!"

# ── 2) Drop privileges & start FastAPI in foreground with optimizations ────
# Use production settings for uvicorn to reduce resource usage
exec gosu "$APP_USER" uvicorn src.main:app \
        --host 0.0.0.0 --port 8000 \
        --workers 1 \
        --limit-concurrency 20 \
        --timeout-keep-alive 3600 \
        --no-access-log \
        --reload --reload-dir /app/src

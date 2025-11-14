FROM caddy:2-alpine

# Install Python 3
RUN apk add --no-cache python3 py3-pip

# Create working directory
WORKDIR /app

# Copy generator script and Caddyfile
COPY generator.py /app/generator.py
COPY Caddyfile /etc/caddy/Caddyfile
COPY entrypoint.sh /app/entrypoint.sh

# Make scripts executable
RUN chmod +x /app/generator.py /app/entrypoint.sh

# Create volume mount points
VOLUME ["/input", "/output"]

# Expose HTTP port
EXPOSE 80

# Run entrypoint script
ENTRYPOINT ["/app/entrypoint.sh"]

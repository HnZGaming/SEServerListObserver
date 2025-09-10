FROM python:3.9-slim
WORKDIR /app


# Install cron, dos2unix, procps (for ps command), and postgresql-client (for pg_isready, psql)
RUN apt-get update && apt-get install -y cron dos2unix procps postgresql-client && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

# Add crontab file
COPY crontab /etc/cron.d/observer-cron
RUN dos2unix /etc/cron.d/observer-cron && chmod 0644 /etc/cron.d/observer-cron && crontab /etc/cron.d/observer-cron

# Create log file to be able to run tail
RUN touch /var/log/cron.log

# Add entrypoint script
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]

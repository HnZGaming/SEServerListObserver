
# Space Engineers Server List Observer


This project monitors the player population of all public Space Engineers community servers and periodically writes player counts to an InfluxDB database. It is designed to run via Docker Compose, supports scheduled polling via cron, and includes integrated Grafana dashboards for data visualization.

This tool allows you to observe the player count of each host, not limited to each host:port. This is important when you want to know the true population of a Nexus-enabled SE community as opposed to a single server instance.


## Features
- Polls all public Space Engineers servers using the Steam master server API
- Collects player counts per host:ip and also per host
- Stores results in InfluxDB (configurable via environment variables)
- Runs easily with Docker Compose (Python + InfluxDB + Grafana)
- Thread-safe, parallelized polling for fast data collection
- Supports scheduled polling via cron (default: every 5 minutes)
- Integrated Grafana dashboards for data visualization (sample dashboard included)

## Getting Started

### Prerequisites
- [Docker](https://www.docker.com/) and [Docker Compose](https://docs.docker.com/compose/)

### Quick Start
1. Clone this repository.
2. Create a `.env` file in the project root with the following variables (adjust values as needed):
   - `INFLUXDB_TOKEN`
   - `INFLUXDB_ORG`
   - `INFLUXDB_BUCKET`
   - `MODE` (set to `dev` for development, `prod` for production)
   
   The `.env` file is automatically used by Docker Compose to provide environment variables, so you do not need to set them manually.

   > **Note:** The default environment variables and Docker Compose configuration use credentials that are intended for local development only. **Do not expose your InfluxDB instance to the public internet or untrusted networks without changing these credentials and securing access.**
3. Start the stack (for development mode):
   ```sh
   MODE=dev docker-compose up --build # bash
   $env:MODE="dev"; docker compose up --build # powershell
   ```
   This will start the observer in development mode, running the polling script once per container start. For production (scheduled polling), set `MODE=prod` in your `.env` file or environment, or don't set `MODE` at all.
4. The observer will poll all regions and ingest results into InfluxDB. In production mode, polling is scheduled automatically every 5 minutes via cron.

### InfluxDB
InfluxDB is started automatically via Docker Compose. Credentials and setup are controlled by environment variables in `docker-compose.yml` and `.env`.


### Data Visualization
Grafana is integrated for advanced and customizable dashboards. A sample dashboard is included and automatically provisioned via the files in `grafana/provisioning/`. Access Grafana at `http://localhost:3001` (default credentials: `admin`/`admin`).

See the included sample dashboard (`grafana/provisioning/dashboards/player_counts.json`) for a quick start.


## Project Structure
- `main.py` — Main polling and ingestion script
- `requirements.txt` — Python dependencies
- `docker-compose.yml` — Multi-container orchestration (Observer + InfluxDB + Grafana)
- `Dockerfile` — Container build for the observer
- `entrypoint.sh` — Entrypoint script for container (handles dev/prod mode and cron)
- `crontab` — Cron schedule (default: every 5 minutes)
- `.env` — Environment variables for configuration
- `grafana/provisioning/` — Provisioned Grafana dashboards and datasources (sample dashboard included)
- `postgres_schema.sql` — Example schema for optional PostgreSQL support
- `init_postgres.sh` — Initialization script for optional PostgreSQL support


## How it Works
1. The observer queries the Steam master server for all Space Engineers servers in all regions.
2. Each server is queried for player count and info in parallel (using reactivex and thread pool).
3. Results are written to InfluxDB as time series data.
4. In production mode, polling is triggered by cron every 5 minutes; in development mode, it runs once per container start.
5. Data is visualized in Grafana using the included sample dashboard.


## Customization
- Polling interval is controlled by the `crontab` file (default: every 5 minutes). You can edit this file to change the schedule.
- InfluxDB, Grafana, and observer settings can be changed via environment variables in `.env`.

## License
MIT License

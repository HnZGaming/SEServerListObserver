# Space Engineers Server Observer

This project will monitor the player population of all public Space Engineers community servers and track the number every N minutes/hours into an InfluxDB instance. It is designed to be run with Docker Compose and is ready for future expansion (e.g., Grafana integration).

## Features
- Python-based server polling
- Docker Compose setup
- Ready for InfluxDB integration

## Getting Started

1. Build and run with Docker Compose:
   ```sh
   docker-compose up --build
   ```

2. (Planned) Configure InfluxDB and Grafana for data visualization.

## Structure
- `main.py`: Main polling script
- `requirements.txt`: Python dependencies
- `docker-compose.yml`: Multi-container orchestration

---

Replace this README as the project evolves.

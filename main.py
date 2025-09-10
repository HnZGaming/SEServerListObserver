import valve.source.master_server
import a2s
from datetime import datetime
import time
import threading
from threading import Lock
import multiprocessing
import reactivex as rx
from reactivex import operators as ops
from reactivex.scheduler import ThreadPoolScheduler
from influxdb_client import InfluxDBClient, Point, WritePrecision
import os
import logging


import psycopg2
import psycopg2.extras

# Setup logging so only logs from this file are output
MODE = os.getenv("MODE", "prod").lower()
ROOT_LEVEL = logging.WARNING  # Suppress logs from other modules
MAIN_LEVEL = logging.DEBUG if MODE != "prod" else logging.INFO
LOG_FORMAT = "[%(levelname)s] %(asctime)s %(message)s"
LOG_DATEFMT = "%Y-%m-%d %H:%M:%S"

# Set root logger to WARNING
logging.basicConfig(level=ROOT_LEVEL, format=LOG_FORMAT, datefmt=LOG_DATEFMT)

# Set a module-specific logger for this file
logger = logging.getLogger(__name__)
logger.setLevel(MAIN_LEVEL)

# https://github.com/serverstf/python-valve
REGIONS = ["na-east", "na-west", "na", "sa", "eu", "as", "oc", "af", "rest"]

servers = []

def list_servers(region):
    logger.info(f"listing servers in region {region}...")
    # https://github.com/serverstf/python-valve
    try:
        with valve.source.master_server.MasterServerQuerier() as msq:
            for server in msq.find(region=region, appid='244850'):
                yield server, region
    except Exception as e:
        logger.error(f"region {region}: {e}")
        yield []

def read_server(address):
    try:
        # https://github.com/Yepoleb/python-a2s
        info = a2s.info(address[0])
        info.address = address

        # get the real steam user count
        players = a2s.players(address[0])
        info.player_count = len(players)
        return [info]
    except Exception as e:
        if 'timed out' in str(e):
            logger.debug(f"{address}: {e}")
        else:
            logger.error(f"{address}: {e}")
        return []

def on_next(info):
    # https://github.com/Yepoleb/python-a2s
    logger.debug(f"{info.address} - {info.server_name}, {info.player_count}/{info.max_players}")

    global servers
    servers.append(info)

def ingest_servers(now):
    logger.info(f"Ingesting {len(servers)} servers into InfluxDB...")

    # Load variables
    influxdb_url = os.environ["INFLUXDB_URL"]
    influxdb_token = os.environ["INFLUXDB_TOKEN"]
    influxdb_org = os.environ["INFLUXDB_ORG"]
    influxdb_bucket = os.environ["INFLUXDB_BUCKET"]

    pg_user = os.environ["POSTGRES_USER"]
    pg_password = os.environ["POSTGRES_PASSWORD"]
    pg_db = os.environ["POSTGRES_DB"]
    pg_port = os.environ["POSTGRES_PORT"]
    pg_host = os.environ["POSTGRES_HOST"]
    
    # Connect to PostgreSQL
    pg_conn = psycopg2.connect(dbname=pg_db, user=pg_user, password=pg_password, host=pg_host, port=pg_port)
    pg_conn.autocommit = True
    pg_cur = pg_conn.cursor()

    # Prepare data for batch upsert
    pg_values = []
    influxdb_points = []
    for info in servers:
        ((ip, port), region) = info.address
        server_name = info.server_name
        player_count = info.player_count
        if ip is None or port is None or player_count is None:
            logger.warning(f"Skipping server with incomplete info: {server_name}, {ip}:{port}, {player_count}")
            continue

        influxdb_point = (
            Point("player_counts")
                .tag("ip", ip)
                .tag("address", f"{ip}:{port}")
                .field("player_count", int(player_count))
                .time(now, WritePrecision.S)
        )
        influxdb_points.append(influxdb_point)
        pg_values.append((ip, port, server_name, region))

    # Batch upsert server metadata
    if pg_values:
        try:
            psycopg2.extras.execute_values(
                pg_cur,
                """
                INSERT INTO servers (ip, port, name, region)
                VALUES %s
                ON CONFLICT (ip, port) DO UPDATE
                SET name = EXCLUDED.name, region = EXCLUDED.region
                """,
                pg_values
            )
        except Exception as e:
            logger.error(f"PostgreSQL batch insert failed: {e}")

    # Batch write points to InfluxDB
    if influxdb_points:
        with InfluxDBClient(url=influxdb_url, token=influxdb_token, org=influxdb_org) as client:
            write_api = client.write_api()
            write_api.write(bucket=influxdb_bucket, org=influxdb_org, record=influxdb_points)
            write_api.close()

    # Close PostgreSQL connection
    pg_cur.close()
    pg_conn.close()

    logger.info(f"Ingestion complete; influxdb: {len(influxdb_points)}, postgres: {len(pg_values)}")

if __name__ == "__main__":
    logger.info("Space Engineers Server Observer starting...")

    start_time = time.perf_counter()
    pool = ThreadPoolScheduler(multiprocessing.cpu_count() * 50)
    done_event = threading.Event()

    def on_completed(e):
        done_event.set()

        if e:
            logger.error(f"Discovery error; error: {e}")
            return

        elapsed = time.perf_counter() - start_time
        logger.info(f"Discovery complete; elapsed: {elapsed:.2f} seconds")

    rx.from_(REGIONS).pipe(
        ops.flat_map(lambda r: rx.from_callable(lambda: list_servers(r), scheduler=pool)),
        ops.flat_map(rx.from_),
        ops.flat_map(lambda a: rx.from_callable(lambda: read_server(a), scheduler=pool)),
        ops.flat_map(rx.from_)
    ).subscribe(
        on_next=lambda i: on_next(i),
        on_error=lambda e: on_completed(e),
        on_completed=lambda: on_completed(None)
    )

    done_event.wait()
    ingest_servers(int(time.time()))
    logger.info("All done")

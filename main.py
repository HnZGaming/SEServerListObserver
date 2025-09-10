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

# Setup logging so only logs from this file are output
MODE = os.getenv("MODE", "prod").lower()
ROOT_LEVEL = logging.WARNING  # Suppress logs from other modules
MAIN_LEVEL = logging.DEBUG if MODE != "prod" else logging.INFO
LOG_FORMAT = "[%(levelname)s] %(asctime)s %(threadName)s %(message)s"
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
                yield server
    except Exception as e:
        logger.error(f"region {region}: {e}")
        yield []

def read_server(address):
    try:
        # https://github.com/Yepoleb/python-a2s
        info = a2s.info(address)
        info.address = address
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

    url = os.getenv("INFLUXDB_URL")
    token = os.getenv("INFLUXDB_TOKEN")
    org = os.getenv("INFLUXDB_ORG")
    bucket = os.getenv("INFLUXDB_BUCKET")

    if not url or not token or not org or not bucket:
        logger.critical(f"Missing required environment variables")
        raise SystemExit(1)

    logger.info(f"ENV INFLUXDB_URL={url}")
    logger.info(f"ENV INFLUXDB_TOKEN={token}")
    logger.info(f"ENV INFLUXDB_ORG={org}")
    logger.info(f"ENV INFLUXDB_BUCKET={bucket}")

    with InfluxDBClient(url=url, token=token, org=org) as client:
        write_api = client.write_api()
        points = []
        for info in servers:
            ip = info.address[0]
            port = info.address[1]
            player_count = info.player_count
            if ip is None or port is None or player_count is None:
                logger.warning(f"Skipping server with incomplete info: {info.server_name}, {ip}:{port}, {player_count}")
                continue

            point = (
                Point("player_counts")
                    .tag("ip", ip)
                    .tag("address", f"{ip}:{port}")
                    .field("player_count", int(player_count))
                    .time(now, WritePrecision.S)
            )

            points.append(point)

        if not points:
            logger.warning("No points ingested")

        write_api.write(bucket=bucket, org=org, record=points)
        write_api.close()

    logger.info("Ingestion complete.")

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

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

s_print_lock = Lock()
def s_print(*a, **b):
    """Thread safe print function"""
    with s_print_lock:
        print(*a, **b)

# https://github.com/serverstf/python-valve
REGIONS = ["na-east", "na-west", "na", "sa", "eu", "as", "oc", "af", "rest"]

servers = []

def list_servers(region):
    s_print(f"[INFO] listing servers in region {region}...")
    
    # https://github.com/serverstf/python-valve
    try:
        with valve.source.master_server.MasterServerQuerier() as msq:
            for server in msq.find(region=region, appid='244850'):
                yield server
    except Exception as e:
        s_print(f"[ERROR] region {region}: {e}")
        yield []

def read_server(address):
    try:
        # https://github.com/Yepoleb/python-a2s
        info = a2s.info(address)
        info.address = address
        return [info]
    except Exception as e:
        s_print(f"[ERROR] {address}: {e}")
        return []

def on_next(info):
    # https://github.com/Yepoleb/python-a2s
    s_print(f"[INFO] {info.address} - {info.server_name}, {info.player_count}/{info.max_players}")

    global servers
    servers.append(info)

def ingest_servers(now):
    s_print(f"[INFO] Ingesting {len(servers)} servers into InfluxDB...")
    url = os.getenv("INFLUXDB_URL", "http://localhost:8086")
    token = os.getenv("INFLUXDB_TOKEN", "se-observer-token")
    org = os.getenv("INFLUXDB_ORG", "se-observer")
    bucket = os.getenv("INFLUXDB_BUCKET", "se-servers")

    with InfluxDBClient(url=url, token=token, org=org) as client:
        write_api = client.write_api()
        points = []
        for info in servers:
            ip = info.address[0]
            port = info.address[1]
            player_count = info.player_count
            if ip is None or port is None or player_count is None:
                s_print(f"[WARN] Skipping server with incomplete info: {info.server_name}, {ip}:{port}, {player_count}")
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
            s_print(f"[WARN] No points ingested")

        write_api.write(bucket=bucket, org=org, record=points)
        write_api.close()

    s_print(f"[INFO] Ingestion complete.")

if __name__ == "__main__":
    s_print("Space Engineers Server Observer starting...")

    start_time = time.perf_counter()
    pool = ThreadPoolScheduler(multiprocessing.cpu_count() * 50)
    done_event = threading.Event()

    def on_completed(e):
        elapsed = time.perf_counter() - start_time
        tag = "ERROR" if e else "INFO"
        s_print(f"[{tag}] Discovery complete; elapsed: {elapsed:.2f} seconds; error: {e}")
        done_event.set()

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
    s_print(f"[INFO] All done")

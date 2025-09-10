import valve.source.master_server
import a2s
import time
import threading
from threading import Lock
import multiprocessing
import reactivex as rx
from reactivex import operators as ops
from reactivex.scheduler import ThreadPoolScheduler

s_print_lock = Lock()
def s_print(*a, **b):
    """Thread safe print function"""
    with s_print_lock:
        print(*a, **b)

# https://github.com/serverstf/python-valve
REGIONS = ["na-east", "na-west", "na", "sa", "eu", "as", "oc", "af", "rest"]

def list_servers(region):
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

def process_server(info):
    # https://github.com/Yepoleb/python-a2s
    s_print(f"[INFO] {info.address} - {info.server_name}, {info.player_count}/{info.max_players}")

if __name__ == "__main__":
    s_print("Space Engineers Server Observer starting...")

    start_time = time.perf_counter()
    pool = ThreadPoolScheduler(multiprocessing.cpu_count() * 50)
    done_event = threading.Event()

    def on_completed(e):
        elapsed = time.perf_counter() - start_time
        s_print(f"[INFO] Completed; elapsed: {elapsed:.2f} seconds; error: {e}")
        done_event.set()

    rx.from_(REGIONS).pipe(
        ops.flat_map(lambda r: rx.from_callable(lambda: list_servers(r), scheduler=pool)),
        ops.flat_map(rx.from_),
        ops.flat_map(lambda a: rx.from_callable(lambda: read_server(a), scheduler=pool)),
        ops.flat_map(rx.from_)
    ).subscribe(
        on_next=lambda i: process_server(i),
        on_error=lambda e: on_completed(e),
        on_completed=lambda: on_completed(None)
    )

    try:
        while not done_event.is_set():
            time.sleep(0.5)
    except KeyboardInterrupt:
        s_print("Interrupted by user — exiting.")
import valve.source.master_server
import a2s
import ipaddress

def list_servers():
    # https://github.com/serverstf/python-valve
    with valve.source.master_server.MasterServerQuerier() as msq:
        for server in msq.find(region="all", appid='244850'):
            yield server

def process_server(address):
    # https://github.com/Yepoleb/python-a2s
    info = a2s.info(address)
    print(f"{address} - {info.server_name}, {info.player_count}/{info.max_players}")

if __name__ == "__main__":
    print("Space Engineers Server Observer starting...")
    server_count = 0
    for address in list_servers():
        try:
            process_server(address)
        except Exception as e:
            err_str = str(e)
            print(f"[ERROR] {address} - {err_str}")

        # todo: remove
        server_count += 1
        if server_count >= 5:
            break

    if server_count == 0:
        print("No servers found.")

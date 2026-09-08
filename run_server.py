import ipaddress
import os
import socket
from pathlib import Path

import psutil
import uvicorn


def _usable_lan_ipv4(value: str) -> bool:
    try:
        address = ipaddress.ip_address(value)
    except ValueError:
        return False
    return (
        address.version == 4
        and address.is_private
        and not address.is_loopback
        and not address.is_link_local
    )


def get_lan_ip() -> str:
    configured = os.getenv("SIH_LAN_IP", "").strip()
    if configured:
        if not _usable_lan_ipv4(configured):
            raise SystemExit("SIH_LAN_IP must be a private, non-loopback IPv4 address.")
        return configured

    # UDP connect selects the host's default route without sending application data.
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
            probe.connect(("192.0.2.1", 9))
            candidate = probe.getsockname()[0]
            if _usable_lan_ipv4(candidate):
                return candidate
    except OSError:
        pass

    try:
        for addresses in psutil.net_if_addrs().values():
            for address in addresses:
                candidate = address.address.split("%", 1)[0]
                if address.family == socket.AF_INET and _usable_lan_ipv4(candidate):
                    return candidate
    except OSError:
        pass

    try:
        addresses = socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET)
        return next(
            address[4][0]
            for address in addresses
            if _usable_lan_ipv4(address[4][0])
        )
    except (OSError, StopIteration):
        return "127.0.0.1"


def get_port() -> int:
    try:
        port = int(os.getenv("SIH_SERVER_PORT", "8000"))
    except ValueError as exc:
        raise SystemExit("SIH_SERVER_PORT must be a number.") from exc
    if not 1 <= port <= 65535:
        raise SystemExit("SIH_SERVER_PORT must be between 1 and 65535.")
    return port

def main():
    lan_ip = get_lan_ip()
    port = get_port()
    host = os.getenv("SIH_SERVER_HOST", "0.0.0.0")
    cert_path = os.getenv("SIH_TLS_CERT_FILE")
    key_path = os.getenv("SIH_TLS_KEY_FILE")
    if bool(cert_path) != bool(key_path):
        raise SystemExit("Set both SIH_TLS_CERT_FILE and SIH_TLS_KEY_FILE, or neither.")
    if cert_path and (not Path(cert_path).is_file() or not Path(key_path).is_file()):
        raise SystemExit("The configured TLS certificate or key file does not exist.")
    scheme = "https" if cert_path else "http"
    
    print("=" * 70)
    print("  SIH LOCAL AI WORKBENCH - MULTI-CLIENT SERVER")
    print("=" * 70)
    print(f"[*] Local Host URL   : {scheme}://localhost:{port}")
    print(f"[*] LAN Network URL  : {scheme}://{lan_ip}:{port}")
    print("-" * 70)
    if not cert_path and lan_ip != "127.0.0.1":
        print("[!] LAN traffic is HTTP. Configure SIH_TLS_CERT_FILE and SIH_TLS_KEY_FILE")
        print("    before using the app on an untrusted network.")
    if lan_ip == "127.0.0.1":
        print("[!] No private LAN IPv4 address was detected.")
        print("    127.0.0.1 works only on this computer. Run `ipconfig` and set:")
        print("    $env:SIH_LAN_IP = '192.168.x.x' before starting the server.")
    print("=" * 70)
    
    uvicorn.run(
        "server.main:app",
        host=host,
        port=port,
        log_level="info",
        proxy_headers=False,
        server_header=False,
        date_header=False,
        ssl_certfile=cert_path,
        ssl_keyfile=key_path,
    )

if __name__ == '__main__':
    main()

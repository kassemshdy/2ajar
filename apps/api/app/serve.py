"""Production entrypoint: one dual-stack (IPv4 + IPv6) socket.

Railway health checks arrive over IPv4 while the private network (web → api) uses IPv6. asyncio marks
"::" sockets IPv6-only, so we bind the socket ourselves with IPV6_V6ONLY disabled and hand it to uvicorn.
"""

import os
import socket

import uvicorn


def dual_stack_socket(port: int) -> socket.socket:
    try:
        sock = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
    except OSError:  # host without IPv6: plain IPv4
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(("0.0.0.0", port))  # noqa: S104 (container must listen on all interfaces)
    else:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 0)
        sock.bind(("::", port))
    sock.set_inheritable(True)
    return sock


def main() -> None:  # pragma: no cover - exercised by the container
    sock = dual_stack_socket(int(os.environ.get("PORT", "8000")))
    uvicorn.run("app.main:app", fd=sock.fileno(), access_log=False, log_level="info")


if __name__ == "__main__":  # pragma: no cover
    main()

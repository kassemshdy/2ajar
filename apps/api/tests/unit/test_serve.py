import socket
from typing import Any

import pytest

import app.serve as serve
from app.serve import dual_stack_socket


def _connect(sock: socket.socket, family: socket.AddressFamily, host: str) -> None:
    port = sock.getsockname()[1]
    with socket.socket(family, socket.SOCK_STREAM) as client:
        client.settimeout(2)
        client.connect((host, port))
        conn, _ = sock.accept()
        conn.close()


def test_socket_accepts_ipv4_and_ipv6_when_available() -> None:
    sock = dual_stack_socket(0)
    try:
        sock.listen()
        _connect(sock, socket.AF_INET, "127.0.0.1")
        if sock.family == socket.AF_INET6:
            assert sock.getsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY) == 0
            _connect(sock, socket.AF_INET6, "::1")
    finally:
        sock.close()


def test_falls_back_to_ipv4(monkeypatch: Any) -> None:
    real = socket.socket

    def fake_socket(family: int = socket.AF_INET, *args: Any) -> socket.socket:
        if family == socket.AF_INET6:
            raise OSError(97, "Address family not supported by protocol")
        return real(family, *args)

    monkeypatch.setattr(serve.socket, "socket", fake_socket)
    sock = dual_stack_socket(0)
    try:
        assert sock.family == socket.AF_INET
    finally:
        sock.close()


@pytest.mark.skipif(not socket.has_ipv6, reason="no IPv6 support compiled in")
def test_has_ipv6_flag() -> None:
    assert socket.has_ipv6

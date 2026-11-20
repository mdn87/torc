"""Measure the Linux browser job's file and network boundaries with test-owned witnesses."""

import errno
import json
import socket
import sys
from pathlib import Path


def denied_open(path, mode):
    try:
        with open(path, mode):
            return None
    except OSError as error:
        return errno.errorcode[error.errno]


def denied_connection(address, port):
    try:
        with socket.create_connection((address, port), timeout=2):
            return None
    except OSError as error:
        return errno.errorcode.get(error.errno, str(error))


def check(private_file, external_address, port):
    with socket.socket() as server:
        server.bind(("127.0.0.1", 0))
        server.listen(1)
        with socket.create_connection(server.getsockname(), timeout=2) as client:
            with server.accept()[0] as peer:
                peer.sendall(b"local")
                own_connection = client.recv(5) == b"local"
    interfaces = sorted(name for _, name in socket.if_nameindex())
    default_routes = [
        row
        for row in Path("/proc/net/route").read_text().splitlines()[1:]
        if row.split()[1] == "00000000"
    ]
    return {
        "read_own_file": Path("/work/witness").read_text() == "inside",
        "same_job_connection": own_connection,
        "interfaces": interfaces,
        "ipv4_default_routes": default_routes,
        "private_file_open": denied_open(private_file, "rb"),
        "runtime_open_for_writing": denied_open("/usr/bin/node", "r+b"),
        "input_open_for_writing": denied_open("/work/witness", "r+b"),
        "host_loopback_connect": denied_connection("127.0.0.1", port),
        "external_witness_connect": denied_connection(external_address, port),
    }


if __name__ == "__main__":
    print(json.dumps(check(sys.argv[1], sys.argv[2], int(sys.argv[3]))))

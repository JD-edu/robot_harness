#!/usr/bin/env python3
"""Keyboard client for tcpip_control.py on the 2-wheel robot PC."""

import argparse
import select
import socket
import sys
import termios
import time
import tty


SEND_INTERVAL = 0.10
KEY_TIMEOUT = 0.35


def read_key() -> str | None:
    """Return one available terminal key without blocking."""
    if select.select([sys.stdin], [], [], 0)[0]:
        return sys.stdin.read(1).lower()
    return None


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("host", help="IP address or hostname of the robot PC")
    parser.add_argument("--port", type=int, default=9999, help="TCP port (default: 9999)")
    parser.add_argument(
        "--connect-timeout",
        type=float,
        default=5.0,
        help="connection timeout in seconds (default: 5)",
    )
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("--port must be between 1 and 65535")
    if args.connect_timeout <= 0:
        parser.error("--connect-timeout must be greater than zero")
    if not sys.stdin.isatty():
        raise SystemExit("Run this program in an interactive terminal.")

    print(f"Connecting to {args.host}:{args.port}...")
    try:
        connection = socket.create_connection(
            (args.host, args.port), timeout=args.connect_timeout
        )
    except OSError as exc:
        raise SystemExit(f"Could not connect: {exc}") from exc

    old_settings = termios.tcgetattr(sys.stdin)
    command = "x"
    last_drive_key = 0.0
    last_send = 0.0

    try:
        connection.settimeout(1.0)
        greeting = connection.recv(1024).decode("utf-8", errors="replace").strip()
        if greeting:
            print(greeting)
        connection.setblocking(False)
        tty.setcbreak(sys.stdin.fileno())
        print("W/A/S/D: move | Space or X: stop | Q: quit")

        while True:
            now = time.monotonic()
            key = read_key()
            if key in ("q", "\x03"):
                break
            if key in ("w", "a", "s", "d"):
                command = key
                last_drive_key = now
            elif key in ("x", " "):
                command = "x"
            elif command != "x" and now - last_drive_key > KEY_TIMEOUT:
                command = "x"

            if now - last_send >= SEND_INTERVAL:
                try:
                    connection.sendall(command.encode("ascii"))
                except (BrokenPipeError, ConnectionResetError, OSError) as exc:
                    raise SystemExit(f"Connection to robot was lost: {exc}") from exc
                last_send = now
            time.sleep(0.01)
    finally:
        try:
            connection.setblocking(True)
            connection.settimeout(0.5)
            connection.sendall(b"xq")
        except OSError:
            pass
        connection.close()
        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)
        print("\nDisconnected; stop command sent.")


if __name__ == "__main__":
    main()

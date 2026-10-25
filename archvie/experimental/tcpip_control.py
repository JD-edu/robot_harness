#!/usr/bin/env python3
"""Control the Arduino 2-wheel robot from another PC over a TCP socket."""

import argparse
import select
import signal
import socket
import time

try:
    import serial
    from serial.tools import list_ports
except ImportError as exc:
    raise SystemExit(
        "pyserial is required. Install it with: python3 -m pip install pyserial"
    ) from exc


SEND_INTERVAL = 0.10
COMMAND_TIMEOUT = 0.50
stop_requested = False


def motor_frame(left: int, right: int) -> bytes:
    """Build the exact frame expected by 2wheel_robot.ino."""
    left = max(-255, min(255, left))
    right = max(-255, min(255, right))
    return f"$M,{left & 0xffff:04X},{right & 0xffff:04X}#\n".encode("ascii")


def find_arduino_port() -> str:
    ports = list(list_ports.comports())
    likely = [
        port
        for port in ports
        if any(
            name in (port.description or "").lower()
            for name in ("arduino", "ch340", "usb serial", "usb-serial")
        )
    ]
    if len(likely) == 1:
        return likely[0].device
    if len(ports) == 1:
        return ports[0].device
    choices = ", ".join(port.device for port in ports) or "none found"
    raise SystemExit(
        f"Could not choose an Arduino serial port ({choices}). "
        "Specify one with --serial-port, for example /dev/ttyACM0."
    )


def serve_client(client: socket.socket, arduino: serial.Serial, speed: int) -> None:
    controls = {
        "w": (speed, speed),
        "s": (-speed, -speed),
        "a": (-speed, speed),
        "d": (speed, -speed),
        "x": (0, 0),
        " ": (0, 0),
    }
    command = (0, 0)
    last_command = time.monotonic()
    last_send = 0.0
    client.setblocking(False)
    client.sendall(
        b"Connected: W/A/S/D move, X or Space stops, Q disconnects.\n"
    )

    try:
        while not stop_requested:
            now = time.monotonic()
            readable, _, _ = select.select([client], [], [], 0.02)
            if readable:
                data = client.recv(1024)
                if not data:
                    break
                for byte in data:
                    key = chr(byte).lower()
                    if key == "q":
                        return
                    if key in controls:
                        command = controls[key]
                        last_command = now

            if command != (0, 0) and now - last_command > COMMAND_TIMEOUT:
                command = (0, 0)

            if now - last_send >= SEND_INTERVAL:
                arduino.write(motor_frame(*command))
                last_send = now
    finally:
        arduino.write(motor_frame(0, 0))
        arduino.flush()


def main() -> None:
    global stop_requested
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--serial-port", help="Arduino port (auto-detected if omitted)")
    parser.add_argument("--listen", default="0.0.0.0", help="listen address")
    parser.add_argument("--tcp-port", type=int, default=9999, help="TCP port")
    parser.add_argument("--speed", type=int, default=180, help="PWM from 1 to 255")
    args = parser.parse_args()
    if not 1 <= args.speed <= 255:
        parser.error("--speed must be between 1 and 255")
    if not 1 <= args.tcp_port <= 65535:
        parser.error("--tcp-port must be between 1 and 65535")

    serial_port = args.serial_port or find_arduino_port()
    def request_stop(_signum: int, _frame: object) -> None:
        global stop_requested
        stop_requested = True

    signal.signal(signal.SIGINT, request_stop)
    signal.signal(signal.SIGTERM, request_stop)

    print(f"Opening Arduino on {serial_port} at 115200 baud...")
    with serial.Serial(serial_port, 115200, timeout=0.1) as arduino:
        time.sleep(2.0)  # An Arduino Uno normally resets when serial is opened.
        arduino.reset_input_buffer()
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
            server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server.bind((args.listen, args.tcp_port))
            server.listen(1)
            server.settimeout(0.5)
            print(f"Listening on {args.listen}:{args.tcp_port}")
            print("Waiting for a controller. Press Ctrl-C to stop the server.")
            try:
                while not stop_requested:
                    try:
                        client, address = server.accept()
                    except socket.timeout:
                        continue
                    print(f"Controller connected from {address[0]}:{address[1]}")
                    with client:
                        try:
                            serve_client(client, arduino, args.speed)
                        except (ConnectionError, OSError) as exc:
                            print(f"Controller connection ended: {exc}")
                    print("Controller disconnected; motors stopped.")
            finally:
                arduino.write(motor_frame(0, 0))
                arduino.flush()
                print("Server stopped; motors stopped.")


if __name__ == "__main__":
    main()

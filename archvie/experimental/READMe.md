# 2-wheel robot keyboard control

Upload `2wheel_robot.ino` to the Arduino, then install the Python dependency:

```bash
python3 -m pip install -r requirements.txt
```

Run the controller (the serial port is auto-detected when possible):

```bash
python3 keyboard_control.py
```

If detection is ambiguous, specify the port:

```bash
python3 keyboard_control.py --port /dev/ttyACM0 --speed 180
```

Controls: `W` forward, `S` backward, `A` turn left, `D` turn right,
Space stop, and `Q` quit. Keep a movement key pressed to continue moving. The
controller stops the motors when a movement key has not repeated for 0.35 s,
and the Arduino also has its own 0.5 s command watchdog.

## TCP/IP control from another PC

On the PC connected to the Arduino, start the TCP server:

```bash
python3 tcpip_control.py --serial-port /dev/ttyACM0 --tcp-port 9999
```

Find that PC's IP address (for example, `192.168.1.50`). On another PC on the
same network, copy `tcpip_client.py` to that PC and run:

```bash
python3 tcpip_client.py 192.168.1.50
```

Hold `W`, `A`, `S`, or `D` to move. Press `X` or Space to stop and `Q` to
disconnect. The client sends repeated commands while a key is held and sends a
stop command when the key is released. It needs no third-party Python package.

The motors stop if no movement command arrives for 0.5 s, if the client
disconnects, or if the server exits. Allow TCP port 9999 through the server
PC's firewall if necessary. The connection is not encrypted or authenticated,
so only use it on a trusted local network.

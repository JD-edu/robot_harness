"""Low-speed keyboard mapping; stop when key input has been absent for 0.3 seconds."""
import select
import sys
import termios
import time
import tty

import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist


def main(args=None):
    rclpy.init(args=args)
    node = Node('jdamr_mapping_teleop')
    output = node.create_publisher(Twist, '/cmd_vel', 10)
    saved = termios.tcgetattr(sys.stdin)
    command = Twist()
    last = 0.
    print('Hold w/s: forward/back, a/d: turn; Space: stop; Ctrl+C: quit', flush=True)
    try:
        tty.setraw(sys.stdin.fileno())
        while rclpy.ok():
            if select.select([sys.stdin], [], [], .05)[0]:
                key = sys.stdin.read(1)
                command = Twist()
                if key == '\x03':
                    break
                command.linear.x = {'w': .12, 's': -.08}.get(key, 0.)
                command.angular.z = {'a': .3, 'd': -.3}.get(key, 0.)
                last = time.monotonic()
            if time.monotonic() - last > .3:
                command = Twist()
            output.publish(command)
            rclpy.spin_once(node, timeout_sec=0.)
    except KeyboardInterrupt:
        pass
    finally:
        output.publish(Twist())
        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, saved)
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()

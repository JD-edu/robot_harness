"""Select harness/Nav2 commands; the physical JDAMR Collision Monitor is downstream."""
import math
import time

import rclpy
from rclpy.clock import Clock, ClockType
from rclpy.node import Node
from geometry_msgs.msg import Twist
from std_srvs.srv import SetBool


class VelocityMux(Node):
    def __init__(self):
        super().__init__('jdamr_velocity_mux')
        self.fine = True
        self.commands = {}
        self.output = self.create_publisher(Twist, '/jdamr_harness/selected_cmd_vel', 10)
        self.create_subscription(Twist, '/slam_harness/nav_cmd_vel', self.nav, 10)
        self.create_subscription(Twist, '/slam_harness/fine_cmd_vel', self.fine_command, 10)
        self.create_service(SetBool, '/slam_harness/fine_control', self.set_mode)
        self.create_timer(.05, self.tick, clock=Clock(clock_type=ClockType.STEADY_TIME))

    def nav(self, msg):
        self.commands['nav'] = (time.monotonic(), msg)

    def fine_command(self, msg):
        self.commands['fine'] = (time.monotonic(), msg)

    def set_mode(self, request, response):
        self.fine = request.data
        self.commands.clear()
        self.output.publish(Twist())
        response.success = True
        return response

    def tick(self):
        stamp, command = self.commands.get('fine' if self.fine else 'nav', (0., Twist()))
        result = Twist()
        values = (command.linear.x, command.linear.y, command.linear.z,
                  command.angular.x, command.angular.y, command.angular.z)
        if time.monotonic() - stamp <= .3 and all(math.isfinite(v) for v in values):
            result.linear.x = max(-.08, min(.12, command.linear.x))
            result.angular.z = max(-.3, min(.3, command.angular.z))
        self.output.publish(result)


def main(args=None):
    rclpy.init(args=args)
    node = VelocityMux()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.output.publish(Twist())
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()

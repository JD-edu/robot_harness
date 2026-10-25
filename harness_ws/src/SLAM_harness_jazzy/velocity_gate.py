"""5. 속도 게이트: 사용할 속도 하나를 선택하고 센서/명령이 끊기면 정지합니다."""
import math
import time
import rclpy
from rclpy.node import Node
from rclpy.clock import Clock, ClockType
from rclpy.qos import qos_profile_sensor_data
from rclpy.time import Time
from geometry_msgs.msg import Twist
from sensor_msgs.msg import LaserScan
from std_srvs.srv import SetBool
from tf2_ros import Buffer, TransformListener, TransformException


class VelocityGate(Node):
    def __init__(self):
        super().__init__('slam_velocity_gate')
        # 시작 시 미세 제어 모드에서 대기합니다. 미션이 시작되면 Nav2로 전환합니다.
        self.fine = True
        self.commands = {}
        self.scan = None
        self.scan_received = 0.
        self.buffer = Buffer()
        self.listener = TransformListener(self.buffer, self)
        self.output = self.create_publisher(Twist, '/cmd_vel', 10)
        self.create_subscription(Twist, '/slam_harness/nav_cmd_vel', self.receive_nav, 10)
        self.create_subscription(Twist, '/slam_harness/fine_cmd_vel', self.receive_fine, 10)
        self.create_subscription(LaserScan, '/scan', self.receive_scan, qos_profile_sensor_data)
        self.create_service(SetBool, '/slam_harness/fine_control', self.set_mode)
        # Gazebo가 일시정지해도 감시는 계속되어야 하므로 실제 경과시간 시계를 씁니다.
        watchdog_clock = Clock(clock_type=ClockType.STEADY_TIME)
        self.create_timer(0.05, self.tick, clock=watchdog_clock)

    def receive_nav(self, message):
        self.receive('nav', message)

    def receive_fine(self, message):
        self.receive('fine', message)

    def receive(self, source, message):
        # 마지막 수신 시각과 속도를 함께 저장합니다.
        self.commands[source] = (time.monotonic(), message)

    def receive_scan(self, scan):
        self.scan = scan
        self.scan_received = time.monotonic()

    def set_mode(self, request, response):
        self.fine = request.data
        self.commands.clear()  # 제어권 전환 전에 받은 속도는 다시 사용하지 않습니다.
        self.output.publish(Twist())
        response.success = True
        return response

    def clear_scan(self, command):
        """라이다 점을 로봇 기준 좌표로 바꾸고 가까운 장애물을 검사합니다."""
        if self.scan is None or time.monotonic() - self.scan_received > 0.5:
            return False
        scan = self.scan
        age = (self.get_clock().now().nanoseconds - Time.from_msg(scan.header.stamp).nanoseconds) / 1e9
        if not -0.2 <= age <= 0.5:
            return False
        try:
            tf = self.buffer.lookup_transform('base_footprint', scan.header.frame_id, Time())
        except TransformException:
            return False
        q = tf.transform.rotation
        yaw = math.atan2(2*(q.w*q.z + q.x*q.y), 1-2*(q.y*q.y+q.z*q.z))
        tx = tf.transform.translation.x
        ty = tf.transform.translation.y
        valid = 0
        for i, distance in enumerate(scan.ranges):
            if math.isnan(distance) or distance < scan.range_min:
                return False  # 잘못된 측정값으로는 안전한 거리를 확인할 수 없습니다.
            if math.isinf(distance) or distance > scan.range_max:
                valid += 1
                continue
            valid += 1
            angle = scan.angle_min + i*scan.angle_increment + yaw
            x = tx + distance * math.cos(angle)
            y = ty + distance * math.sin(angle)
            # 로봇 반경 0.32m + 여유 0.08m 이내의 장애물을 확인합니다.
            # 가까운 장애물 쪽 이동/회전은 막고, 멀어지는 직선 이동은 허용합니다.
            if math.hypot(x, y) < 0.40:
                if abs(command.angular.z) > 0.01 or x*command.linear.x >= 0:
                    return False
        return valid > 0

    def tick(self):
        """0.05초마다 호출: 제어권 선택 → 시간/센서 검사 → 속도 전달."""
        source = 'nav'
        if self.fine:
            source = 'fine'
        stamp, command = self.commands.get(source, (0, Twist()))

        # 1. 명령이 0.3초 이상 오지 않으면 정지합니다.
        if time.monotonic() - stamp > 0.3:
            self.output.publish(Twist())
            return
        # 2. 잘못된 숫자나 오래된 센서 데이터로는 이동하지 않습니다.
        if not math.isfinite(command.linear.x) or not math.isfinite(command.angular.z):
            self.output.publish(Twist())
            return
        if not self.clear_scan(command):
            self.output.publish(Twist())
            return

        # 3. 차동구동 로봇에서 쓰는 전후진 속도와 회전 속도만 전달합니다.
        result = Twist()
        result.linear.x = max(-0.15, min(0.22, command.linear.x))
        result.angular.z = max(-0.6, min(0.6, command.angular.z))
        self.output.publish(result)


def main(args=None):
    rclpy.init(args=args)
    node = VelocityGate()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.output.publish(Twist())
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()

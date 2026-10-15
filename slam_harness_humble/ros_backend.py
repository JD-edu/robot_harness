"""4. ROS 2 담당: Nav2에 목표 보내기, 결과 확인, 시간 초과 취소, 정지."""
import math
import time

import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient
from rclpy.time import Time
from action_msgs.msg import GoalStatus
from nav2_msgs.action import NavigateToPose
from geometry_msgs.msg import PoseStamped, Twist
from std_srvs.srv import SetBool
from tf2_ros import Buffer, TransformListener, TransformException

from .locations import Pose
from .fine_controller import control


class ROSSkills(Node):
    def __init__(self, nav_timeout=120.0, align_timeout=25.0, retreat_timeout=40.0):
        super().__init__('robot_mission_harness')
        self.nav_timeout = nav_timeout
        self.align_timeout = align_timeout
        self.retreat_timeout = retreat_timeout

        # 액션: 시간이 걸리는 이동을 요청하고 진행 상태와 최종 결과를 받습니다.
        self.nav = ActionClient(self, NavigateToPose, 'navigate_to_pose')
        # TF: 지도에서 현재 로봇 위치를 읽습니다.
        self.buffer = Buffer()
        self.listener = TransformListener(self.buffer, self)
        # 토픽: 미세 정렬 속도. 서비스: Nav2/미세 정렬의 제어권 선택.
        self.publisher = self.create_publisher(Twist, '/slam_harness/fine_cmd_vel', 10)
        self.mode = self.create_client(SetBool, '/slam_harness/fine_control')

        self.active = None  # 현재 수락된 Nav2 목표 핸들
        self.unsafe = False  # 취소 여부를 확인할 수 없으면 후속 이동 금지
        self.control_started = False
        self.last_tf_stamp = None
        self.last_tf_wall = time.monotonic()
        self.last_progress_time = time.monotonic()
        self.last_progress_position = None

    def on_arrival(self, name):
        """테이블 방문 후 할 작업. 현재는 로그만 출력합니다."""
        self.get_logger().info(f'{name}: 방문 완료, 도착 콜백 실행')

    def wait(self, future, timeout):
        """비동기 응답을 기다리면서 ROS 메시지도 계속 처리합니다."""
        deadline = time.monotonic() + timeout
        while rclpy.ok() and not future.done():
            if time.monotonic() >= deadline:
                break
            rclpy.spin_once(self, timeout_sec=0.05)
        if not future.done():
            raise TimeoutError('ROS response deadline exceeded')
        return future.result()

    def fine_control(self, enabled):
        """True: 미세 정렬 제어, False: Nav2 제어. 전환 시 게이트가 이전 속도를 버립니다."""
        if not self.mode.wait_for_service(timeout_sec=3.0):
            raise RuntimeError('velocity gate unavailable')
        request = SetBool.Request()
        request.data = enabled
        future = self.mode.call_async(request)
        result = self.wait(future, 3.0)
        if not result.success:
            raise RuntimeError(result.message)
        self.control_started = True

    def stop(self):
        # 기본 Twist의 모든 속도는 0입니다.
        self.publisher.publish(Twist())

    def shutdown_motion(self):
        """미션 종료 시 취소와 정지를 시도합니다. 서버가 없어도 원래 결과는 보존합니다."""
        try:
            self.cancel()
        except Exception as error:
            self.get_logger().error(f'종료 중 Nav2 취소 확인 실패: {error}')
        try:
            if self.control_started:
                self.fine_control(True)
        except Exception as error:
            self.get_logger().warning(f'종료 중 속도 게이트 연결 실패: {error}')
        finally:
            self.stop()

    def cancel(self):
        """취소 요청뿐 아니라 최종 결과까지 확인해야 다음 이동을 시작할 수 있습니다."""
        if self.active is None:
            return
        try:
            self.wait(self.active.cancel_goal_async(), 3.0)
            terminal = self.wait(self.active.get_result_async(), 5.0)
            if terminal.status not in (
                GoalStatus.STATUS_SUCCEEDED,
                GoalStatus.STATUS_CANCELED,
                GoalStatus.STATUS_ABORTED,
            ):
                raise RuntimeError('goal is not terminal')
            self.active = None
        except Exception:
            self.unsafe = True
            try:
                self.fine_control(True)
            finally:
                self.stop()
            raise

    def create_goal(self, target):
        """x, y, yaw를 Nav2가 받는 PoseStamped 메시지로 바꿉니다."""
        pose = PoseStamped()
        pose.header.frame_id = 'map'
        pose.header.stamp = self.get_clock().now().to_msg()
        pose.pose.position.x = target.x
        pose.pose.position.y = target.y
        # 평면 회전 yaw를 quaternion의 z, w로 변환합니다.
        pose.pose.orientation.z = math.sin(target.yaw / 2.0)
        pose.pose.orientation.w = math.cos(target.yaw / 2.0)
        goal = NavigateToPose.Goal()
        goal.pose = pose
        return goal

    def receive_feedback(self, message):
        """5cm 이상 이동할 때마다 진행 시각을 갱신해 정체를 감시합니다."""
        position = message.feedback.current_pose.pose.position
        moved = self.last_progress_position is None
        if self.last_progress_position is not None:
            old_x, old_y = self.last_progress_position
            distance = math.hypot(position.x - old_x, position.y - old_y)
            moved = distance >= 0.05
        if moved:
            self.last_progress_time = time.monotonic()
            self.last_progress_position = (position.x, position.y)

    def cancel_late_goal(self, future):
        """수락 응답이 늦게 와도 뒤늦은 목표를 취소합니다. 게이트는 잠긴 상태입니다."""
        handle = future.result()
        if handle is not None and handle.accepted:
            handle.cancel_goal_async()

    def wait_for_navigation(self, future):
        """도착/실패 결과, 전체 제한시간, 20초 정체를 함께 확인합니다."""
        deadline = time.monotonic() + self.nav_timeout
        while rclpy.ok() and not future.done():
            rclpy.spin_once(self, timeout_sec=0.05)
            if time.monotonic() > deadline:
                self.cancel()
                return 'timeout'
            if time.monotonic() - self.last_progress_time > 20.0:
                self.cancel()
                return 'stalled'

        if not rclpy.ok():
            self.cancel()
            return 'canceled'

        response = future.result()
        self.active = None
        if response.status == GoalStatus.STATUS_SUCCEEDED:
            # Humble의 일부 버전에는 error_code 필드가 없습니다.
            if getattr(response.result, 'error_code', 0) != 0:
                return 'aborted'
            return 'succeeded'
        if response.status == GoalStatus.STATUS_CANCELED:
            return 'canceled'
        if response.status == GoalStatus.STATUS_ABORTED:
            return 'aborted'
        return 'unknown'

    def move_to(self, target):
        """일반 이동의 흐름: 서버 확인 → 제어권 선택 → 목표 전송 → 결과 대기."""
        self.get_logger().info(f'move_to: {target}')
        if self.unsafe:
            return 'unsafe'
        if not self.nav.wait_for_server(timeout_sec=10.0):
            self.get_logger().error(
                'Nav2 /navigate_to_pose 서버를 찾을 수 없습니다. '
                'ros2 launch ros_dd_navigation three_tables_navigation.launch.py를 실행하고 '
                '두 터미널의 ROS_DOMAIN_ID가 같은지 확인하세요.')
            return 'unavailable'
        try:
            self.fine_control(False)
        except (RuntimeError, TimeoutError) as error:
            self.get_logger().error(f'속도 게이트 연결 실패: {error}')
            return 'gate_unavailable'

        goal = self.create_goal(target)
        self.last_progress_time = time.monotonic()
        self.last_progress_position = None
        pending = self.nav.send_goal_async(goal, feedback_callback=self.receive_feedback)
        try:
            self.active = self.wait(pending, 5.0)
        except TimeoutError:
            # 수락 여부가 불명확하므로 재시도하지 않고 게이트를 잠급니다.
            self.unsafe = True
            pending.add_done_callback(self.cancel_late_goal)
            try:
                self.fine_control(True)
            finally:
                self.stop()
            return 'unsafe'

        if not self.active.accepted:
            self.active = None
            return 'rejected'
        result_future = self.active.get_result_async()
        return self.wait_for_navigation(result_future)

    # 아래부터는 선택 기능입니다. --alignment skip이면 호출하지 않습니다.
    def pose(self):
        """map -> base_footprint TF를 읽고 데이터가 계속 갱신되는지 확인합니다."""
        transform = self.buffer.lookup_transform('map', 'base_footprint', Time())
        stamp = Time.from_msg(transform.header.stamp).nanoseconds
        age = (self.get_clock().now().nanoseconds - stamp) / 1e9
        if not -0.2 <= age <= 0.5:
            raise RuntimeError('map TF stale')
        if stamp != self.last_tf_stamp:
            self.last_tf_stamp = stamp
            self.last_tf_wall = time.monotonic()
        if time.monotonic() - self.last_tf_wall > 0.5:
            raise RuntimeError('map TF stopped updating')

        position = transform.transform.translation
        q = transform.transform.rotation
        yaw = math.atan2(2 * (q.w*q.z + q.x*q.y), 1 - 2 * (q.y*q.y + q.z*q.z))
        return Pose(position.x, position.y, yaw)

    def fine_move(self, target, timeout, reverse=False):
        skill_name = 'align_to'
        if reverse:
            skill_name = 'retreat_to'
        self.get_logger().info(f'{skill_name}: {target}, timeout={timeout}s')
        if self.unsafe or self.active is not None:
            return 'unsafe'
        self.fine_control(True)
        deadline = time.monotonic() + timeout
        stable_since = None
        try:
            while rclpy.ok() and time.monotonic() < deadline:
                rclpy.spin_once(self, timeout_sec=0.05)
                try:
                    current = self.pose()
                except (TransformException, RuntimeError):
                    self.stop()
                    stable_since = None
                    continue
                if math.hypot(target.x - current.x, target.y - current.y) > 1.6:
                    return 'outside_local_area'

                velocity, reached = control(current, target, reverse)
                linear, angular = velocity
                if reached:
                    self.stop()
                    if stable_since is None:
                        stable_since = time.monotonic()
                    if time.monotonic() - stable_since >= 0.5:
                        return 'succeeded'
                else:
                    stable_since = None
                    command = Twist()
                    command.linear.x = linear
                    command.angular.z = angular
                    self.publisher.publish(command)
            return 'timeout'
        finally:
            # 정상 종료와 실패 모두 반드시 정지합니다.
            self.stop()
            # 다음 move_to에서 명시적으로 전환할 때까지 게이트는 미세 제어 모드 유지.

    def backoff(self, distance):
        """실패 당시 로봇 방향 기준으로 뒤로 이동합니다. 테이블 좌표를 쓰지 않습니다."""
        if type(distance) not in (int, float) or not math.isfinite(distance) or not 0.1 <= distance <= 1.5:
            raise ValueError('backoff distance must be within 0.1..1.5 meters')
        if self.unsafe or self.active is not None:
            return 'unsafe'
        deadline = time.monotonic() + 3.0
        while rclpy.ok() and time.monotonic() < deadline:
            rclpy.spin_once(self, timeout_sec=0.05)
            try:
                current = self.pose()
                break
            except (TransformException, RuntimeError):
                self.stop()
        else:
            return 'unavailable' if rclpy.ok() else 'canceled'
        target = Pose(current.x - distance * math.cos(current.yaw),
                      current.y - distance * math.sin(current.yaw), current.yaw)
        try:
            return self.fine_move(target, self.retreat_timeout, reverse=True)
        except (RuntimeError, TimeoutError) as error:
            self.get_logger().error(f'후퇴 제어 실패: {error}')
            self.stop()
            return 'gate_unavailable'

    def align_to(self, target):
        return self.fine_move(target, self.align_timeout)

    def retreat_to(self, target):
        return self.fine_move(target, self.retreat_timeout, reverse=True)

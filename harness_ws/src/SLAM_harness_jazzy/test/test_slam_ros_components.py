"""No ROS graph required: exercise gate and action cancellation using message objects."""
import math
import time
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch

try:
    from geometry_msgs.msg import Twist
    from sensor_msgs.msg import LaserScan
    from std_srvs.srv import SetBool
    from SLAM_harness_jazzy.velocity_gate import VelocityGate
    from SLAM_harness_jazzy.ros_backend import ROSSkills
    ROS_AVAILABLE = True
except ImportError:
    ROS_AVAILABLE = False


@unittest.skipUnless(ROS_AVAILABLE, 'source ROS 2 setup to test ROS components')
class ROSComponentTests(unittest.TestCase):
    def probe(self, ranges=(2.,), offset=0.):
        scan = LaserScan()
        scan.header.stamp.sec = 1
        scan.range_min, scan.range_max = .05, 8.
        scan.ranges = list(ranges)
        tf = NS(transform=NS(translation=NS(x=offset,y=0.),rotation=NS(x=0.,y=0.,z=0.,w=1.)))
        outputs=[]
        probe=NS(scan=scan,scan_received=time.monotonic(),
            buffer=NS(lookup_transform=lambda *_:tf),
            get_clock=lambda:NS(now=lambda:NS(nanoseconds=1_003_000_000)),
            commands={},fine=True, output=NS(publish=outputs.append))
        probe.clear_scan=lambda command:VelocityGate.clear_scan(probe,command)
        probe.outputs=outputs
        return probe

    def test_backoff_uses_current_robot_heading(self):
        from SLAM_harness_jazzy.locations import Pose
        for yaw in (0., math.pi / 2, math.pi):
            calls = []
            p = NS(unsafe=False, active=None, retreat_timeout=40.,
                   pose=lambda: Pose(2., 3., yaw), stop=lambda: None,
                   fine_move=lambda target, timeout, reverse: calls.append((target, timeout, reverse)) or 'succeeded')
            with patch('SLAM_harness_jazzy.ros_backend.rclpy.ok', return_value=True), \
                 patch('SLAM_harness_jazzy.ros_backend.rclpy.spin_once'):
                self.assertEqual(ROSSkills.backoff(p, 1.), 'succeeded')
            target, timeout, reverse = calls[0]
            self.assertAlmostEqual(target.x, 2 - math.cos(yaw))
            self.assertAlmostEqual(target.y, 3 - math.sin(yaw))
            self.assertEqual(target.yaw, yaw)
            self.assertTrue(reverse)
            self.assertEqual(timeout, 40.)

    def test_backoff_refuses_active_goal_and_invalid_distance(self):
        for p in (NS(unsafe=True, active=None), NS(unsafe=False, active=object())):
            self.assertEqual(ROSSkills.backoff(p, 1.), 'unsafe')
        for distance in (0., -1., 2., True, float('nan'), float('inf')):
            with self.subTest(distance=distance), self.assertRaises(ValueError):
                ROSSkills.backoff(NS(), distance)

    def test_backoff_missing_tf_never_moves(self):
        calls = []
        p = NS(unsafe=False, active=None, stop=lambda: calls.append('stop'))
        with patch('SLAM_harness_jazzy.ros_backend.rclpy.ok', return_value=True), \
             patch('SLAM_harness_jazzy.ros_backend.time.monotonic', side_effect=[0, 4]):
            self.assertEqual(ROSSkills.backoff(p, 1.), 'unavailable')

    def test_scan_offset_is_transformed_to_robot_frame(self):
        self.assertFalse(self.probe((.25,)).clear_scan(Twist()))
        self.assertTrue(self.probe((.25,),offset=.3).clear_scan(Twist()))

    def test_stale_and_invalid_scan_block(self):
        for ranges in [(float('nan'),),(0.,),()]:
            self.assertFalse(self.probe(ranges).clear_scan(Twist()))
        p=self.probe();p.scan_received-=1
        self.assertFalse(p.clear_scan(Twist()))
        p=self.probe();p.scan.header.stamp.sec=0
        self.assertFalse(p.clear_scan(Twist()))

    def test_small_clock_message_skew_is_allowed(self):
        p=self.probe();p.get_clock=lambda:NS(now=lambda:NS(nanoseconds=990_000_000))
        self.assertTrue(p.clear_scan(Twist()))

    def test_retreat_away_from_obstacle_is_allowed(self):
        p=self.probe((.3,));cmd=Twist();cmd.linear.x=-.05
        self.assertTrue(p.clear_scan(cmd))
        cmd.linear.x=.05
        self.assertFalse(p.clear_scan(cmd))
        cmd.linear.x=-.05;cmd.angular.z=.1
        self.assertFalse(p.clear_scan(cmd))

    def test_watchdog_and_exclusive_ownership(self):
        p=self.probe();cmd=Twist();cmd.linear.x=.05
        p.commands={'nav':(time.monotonic(),cmd)}
        VelocityGate.tick(p)
        self.assertEqual(p.outputs[-1].linear.x,0.)
        p.fine=False;VelocityGate.tick(p)
        self.assertEqual(p.outputs[-1].linear.x,.05)
        p.commands['nav']=(time.monotonic()-1,cmd);VelocityGate.tick(p)
        self.assertEqual(p.outputs[-1].linear.x,0.)

    def test_mode_switch_discards_previous_commands(self):
        p=self.probe();p.commands={'nav':(time.monotonic(),Twist())}
        response=VelocityGate.set_mode(p,SetBool.Request(data=False),SetBool.Response())
        self.assertTrue(response.success)
        self.assertEqual(p.commands,{})
        self.assertFalse(p.fine)

    def test_cancel_waits_for_terminal_before_releasing_goal(self):
        calls=[]
        handle=NS(cancel_goal_async=lambda:calls.append('cancel') or 'cancel_future',
                  get_result_async=lambda:calls.append('terminal') or 'result_future')
        def wait(future,timeout):
            calls.append(future)
            return NS(status=5)
        p=NS(active=handle,unsafe=False,wait=wait)
        ROSSkills.cancel(p)
        self.assertEqual(calls,['cancel','cancel_future','terminal','result_future'])
        self.assertIsNone(p.active)

    def test_shutdown_without_connection_does_not_request_gate(self):
        calls=[]
        p=NS(control_started=False,cancel=lambda:calls.append('cancel'),
             fine_control=lambda enabled:calls.append('gate'),stop=lambda:calls.append('stop'))
        ROSSkills.shutdown_motion(p)
        self.assertEqual(calls,['cancel','stop'])

    def test_shutdown_reports_disconnected_gate_without_traceback(self):
        calls=[]
        def missing(_):raise RuntimeError('velocity gate unavailable')
        logger=NS(warning=lambda text:calls.append(text),error=lambda text:calls.append(text))
        p=NS(control_started=True,cancel=lambda:None,fine_control=missing,
             stop=lambda:calls.append('stop'),get_logger=lambda:logger)
        ROSSkills.shutdown_motion(p)
        self.assertIn('velocity gate unavailable',calls[0])
        self.assertEqual(calls[-1],'stop')

    def test_unavailable_nav_explains_required_launch(self):
        messages=[]
        logger=NS(info=lambda text:None,error=messages.append)
        p=NS(unsafe=False,nav=NS(wait_for_server=lambda **_:False),get_logger=lambda:logger)
        self.assertEqual(ROSSkills.move_to(p,None),'unavailable')
        self.assertIn('three_tables_navigation.launch.py',messages[0])

    def test_unavailable_gate_is_a_mission_failure(self):
        def missing(_):raise RuntimeError('velocity gate unavailable')
        logger=NS(info=lambda text:None,error=lambda text:None)
        p=NS(unsafe=False,nav=NS(wait_for_server=lambda **_:True),
             fine_control=missing,get_logger=lambda:logger)
        self.assertEqual(ROSSkills.move_to(p,None),'gate_unavailable')

    def test_navigation_result_states(self):
        for status, code, expected in [(4,0,'succeeded'),(4,1,'aborted'),
                                        (5,0,'canceled'),(6,0,'aborted'),(0,0,'unknown')]:
            with self.subTest(status=status,code=code):
                future=NS(done=lambda:True,result=lambda:NS(status=status,result=NS(error_code=code)))
                p=NS(nav_timeout=10,active=object())
                with patch('SLAM_harness_jazzy.ros_backend.rclpy.ok',return_value=True):
                    self.assertEqual(ROSSkills.wait_for_navigation(p,future),expected)
                self.assertIsNone(p.active)

    def test_navigation_timeout_cancels_before_return(self):
        calls=[]
        p=NS(nav_timeout=1,last_progress_time=100,cancel=lambda:calls.append('cancel'))
        future=NS(done=lambda:False)
        with patch('SLAM_harness_jazzy.ros_backend.rclpy.ok',return_value=True), \
             patch('SLAM_harness_jazzy.ros_backend.rclpy.spin_once'), \
             patch('SLAM_harness_jazzy.ros_backend.time.monotonic',side_effect=[0,2]):
            self.assertEqual(ROSSkills.wait_for_navigation(p,future),'timeout')
        self.assertEqual(calls,['cancel'])

    def test_navigation_stall_cancels_before_return(self):
        calls=[]
        p=NS(nav_timeout=120,last_progress_time=0,cancel=lambda:calls.append('cancel'))
        future=NS(done=lambda:False)
        with patch('SLAM_harness_jazzy.ros_backend.rclpy.ok',return_value=True), \
             patch('SLAM_harness_jazzy.ros_backend.rclpy.spin_once'), \
             patch('SLAM_harness_jazzy.ros_backend.time.monotonic',side_effect=[0,21,21]):
            self.assertEqual(ROSSkills.wait_for_navigation(p,future),'stalled')
        self.assertEqual(calls,['cancel'])

    def test_cancel_stops_even_when_gate_request_fails(self):
        calls=[]
        def wait(*_):raise TimeoutError('cancel timed out')
        def missing(_):raise RuntimeError('gate missing')
        p=NS(active=NS(cancel_goal_async=lambda:None),unsafe=False,wait=wait,
             fine_control=missing,stop=lambda:calls.append('stop'))
        with self.assertRaises(RuntimeError):ROSSkills.cancel(p)
        self.assertTrue(p.unsafe)
        self.assertEqual(calls,['stop'])

    def test_unconfirmed_cancel_locks_gate(self):
        calls=[]
        def wait(*_):raise TimeoutError('no response')
        p=NS(active=NS(cancel_goal_async=lambda:None),unsafe=False,wait=wait,
             fine_control=lambda enabled:calls.append(enabled),stop=lambda:calls.append('stop'))
        with self.assertRaises(TimeoutError): ROSSkills.cancel(p)
        self.assertTrue(p.unsafe)
        self.assertEqual(calls,[True,'stop'])


if __name__=='__main__':unittest.main()

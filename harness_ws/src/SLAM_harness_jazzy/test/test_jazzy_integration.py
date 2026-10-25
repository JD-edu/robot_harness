"""Jazzy-specific startup and parameter wiring regressions, without a running graph."""
import importlib.util
from pathlib import Path
from types import SimpleNamespace as NS
import unittest
from unittest.mock import MagicMock, patch

import yaml

try:
    from launch import LaunchContext
    from SLAM_harness_jazzy.ros_backend import ROSSkills
    from SLAM_harness_jazzy.main import read_options, run_ros_mission
    from lifecycle_msgs.msg import State
    from tf2_ros import TransformException
    import ros_dd_navigation.launch_checks
    ROS_AVAILABLE = True
except ImportError:
    ROS_AVAILABLE = False


@unittest.skipUnless(ROS_AVAILABLE, 'source harness_ws/install/setup.bash')
class JazzyStartupTests(unittest.TestCase):
    def test_mission_constructs_backend_with_three_motion_timeouts(self):
        options, _ = read_options(['--plan-json', '{"waypoints":["table_1"]}'])
        with patch('SLAM_harness_jazzy.ros_backend.ROSSkills', autospec=True) as backend, \
             patch('rclpy.init'), patch('rclpy.ok', return_value=True), patch('rclpy.shutdown'):
            backend.return_value.wait_until_ready.return_value = False
            self.assertEqual(run_ros_mission(options, [], {}, ['table_1']), 1)
            backend.assert_called_once_with(120., 25., 40.)
            backend.return_value.wait_until_ready.assert_called_once_with(120.)
            backend.return_value.move_to.assert_not_called()
            backend.return_value.shutdown_motion.assert_called_once()
            backend.return_value.destroy_node.assert_called_once()

    def probe(self, active=True, tf=True):
        state = MagicMock()
        state.wait_for_service.return_value = True
        p = NS(create_client=lambda *_: state, destroy_client=MagicMock(),
               wait=lambda *_: NS(current_state=NS(id=State.PRIMARY_STATE_ACTIVE if active else 2)),
               pose=MagicMock(), nav=MagicMock(), get_logger=MagicMock())
        p.nav.wait_for_server.return_value = True
        if not tf:
            p.pose.side_effect = TransformException('missing TF')
        return p

    def test_readiness_requires_active_lifecycle_and_tf(self):
        for active, tf, expected in ((True, True, True), (False, True, False), (True, False, False)):
            with self.subTest(active=active, tf=tf):
                p = self.probe(active, tf)
                with patch('SLAM_harness_jazzy.ros_backend.rclpy.ok', return_value=True), \
                     patch('SLAM_harness_jazzy.ros_backend.rclpy.spin_once'), \
                     patch('SLAM_harness_jazzy.ros_backend.time.monotonic', side_effect=[0., 0., 0., 2.]):
                    self.assertEqual(ROSSkills.wait_until_ready(p, 1.), expected)
                p.destroy_client.assert_called_once()
                if not active:
                    p.pose.assert_not_called()

    def test_saved_map_initial_pose_inserts_missing_yaml_keys(self):
        path = Path(__file__).resolve().parents[1] / 'launch/three_tables_harness.launch.py'
        spec = importlib.util.spec_from_file_location('jazzy_harness_launch', path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        from ament_index_python.packages import get_package_share_directory
        config = Path(get_package_share_directory('ros_dd_navigation')) / 'config/three_tables_nav2.yaml'
        context = LaunchContext()
        context.launch_configurations.update({
            'mode': 'saved_map', 'map': '/test/map.yaml', 'start_simulation': 'false',
            'params_file': str(config), 'set_initial_pose': 'true',
            'initial_x': '1.25', 'initial_y': '-2.5', 'initial_yaw': '0.75',
        })
        rewritten = []
        original = module.RewrittenYaml
        def record(**kwargs):
            result = original(**kwargs)
            rewritten.append(result)
            return result
        with patch('ros_dd_navigation.launch_checks.assert_mode_available'), \
             patch('ros_dd_navigation.launch_checks.validate_map_file', return_value='/test/map.yaml'), \
             patch.object(module, 'RewrittenYaml', side_effect=record):
            module._start(context)
        output = Path(rewritten[0].perform(context))
        try:
            params = yaml.safe_load(output.read_text())
            amcl = params['amcl']['ros__parameters']
            self.assertIs(amcl['set_initial_pose'], True)
            self.assertEqual(amcl['initial_pose'], {'x': 1.25, 'y': -2.5, 'z': 0., 'yaw': .75})
            for name in ('controller_server', 'behavior_server', 'velocity_smoother'):
                self.assertIs(params[name]['ros__parameters']['enable_stamped_cmd_vel'], False)
        finally:
            output.unlink()


if __name__ == '__main__':
    unittest.main()

"""Verify the mapping -> explicit saved map -> navigation startup contract."""
import importlib.util
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

try:
    from launch import LaunchContext
    from launch.actions import DeclareLaunchArgument
    import ros_dd_navigation.launch_checks
    ROS_AVAILABLE = True
except ImportError:
    ROS_AVAILABLE = False


def load_launch(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@unittest.skipUnless(ROS_AVAILABLE, 'source harness_ws/install/setup.bash')
class SavedMapDefaultTests(unittest.TestCase):
    def setUp(self):
        package = Path(__file__).resolve().parents[1]
        self.module = load_launch(package / 'launch/three_tables_harness.launch.py', 'saved_map_harness_launch')
        self.context = LaunchContext()
        for action in self.module.generate_launch_description().entities:
            if isinstance(action, DeclareLaunchArgument):
                action.execute(self.context)
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.map_path = Path(temporary.name) / 'new_survey.yaml'
        self.map_path.write_text('image: new_survey.pgm\nresolution: 0.05\norigin: [0,0,0]\n')
        self.map_path.with_suffix('.pgm').write_bytes(b'P5\n1 1\n255\n\xff')

    def test_no_map_requires_mapping_first_instead_of_loading_old_bundled_map(self):
        self.assertEqual(self.context.launch_configurations['mode'], 'saved_map')
        self.assertEqual(self.context.launch_configurations['set_initial_pose'], 'false')
        self.assertEqual(self.context.launch_configurations['map'], '')
        with patch('ros_dd_navigation.launch_checks.assert_mode_available') as graph, \
             patch.object(self.module, 'IncludeLaunchDescription') as include:
            with self.assertRaisesRegex(RuntimeError, 'First run ros2 launch ros_dd_navigation three_tables_mapping'):
                self.module._start(self.context)
            graph.assert_not_called()
            include.assert_not_called()

    def test_explicit_new_map_is_used_without_cartographer(self):
        self.context.launch_configurations['map'] = str(self.map_path)
        with patch('ros_dd_navigation.launch_checks.assert_mode_available'), \
             patch.object(self.module, 'IncludeLaunchDescription',
                          wraps=self.module.IncludeLaunchDescription) as include:
            self.module._start(self.context)
        arguments = [dict(call.kwargs['launch_arguments']) for call in include.call_args_list]
        self.assertEqual(len(arguments), 2)
        navigation = next(args for args in arguments if 'use_localization' in args)
        self.assertEqual(navigation['use_localization'], 'true')
        self.assertEqual(navigation['map'], str(self.map_path.resolve()))
        self.assertFalse(any('configuration_basename' in args for args in arguments))

    def test_missing_map_stops_before_any_nodes_or_graph_checks(self):
        self.context.launch_configurations['map'] = str(self.map_path.parent / 'missing.yaml')
        with patch('ros_dd_navigation.launch_checks.assert_mode_available') as graph, \
             patch.object(self.module, 'IncludeLaunchDescription') as include:
            with self.assertRaisesRegex(RuntimeError, 'Map YAML file does not exist'):
                self.module._start(self.context)
            graph.assert_not_called()
            include.assert_not_called()

    def test_missing_image_is_not_replaced_with_another_map(self):
        self.map_path.with_suffix('.pgm').unlink()
        self.context.launch_configurations['map'] = str(self.map_path)
        with patch('ros_dd_navigation.launch_checks.assert_mode_available') as graph:
            with self.assertRaisesRegex(RuntimeError, 'Map image does not exist'):
                self.module._start(self.context)
            graph.assert_not_called()

    def test_mapping_launch_only_starts_simulation_cartographer_and_rviz(self):
        from ament_index_python.packages import get_package_share_directory
        path = Path(get_package_share_directory('ros_dd_navigation')) / 'launch/three_tables_mapping.launch.py'
        mapping = load_launch(path, 'three_table_mapping_launch')
        with patch.object(mapping, 'IncludeLaunchDescription', wraps=mapping.IncludeLaunchDescription) as include, \
             patch.object(mapping, 'Node', wraps=mapping.Node) as node:
            mapping.generate_launch_description()
        arguments = [dict(call.kwargs['launch_arguments']) for call in include.call_args_list]
        self.assertEqual(len(arguments), 2)
        self.assertTrue(any(args.get('configuration_basename') == 'three_tables.lua' for args in arguments))
        self.assertFalse(any('use_localization' in args or 'map' in args for args in arguments))
        self.assertEqual([call.kwargs['package'] for call in node.call_args_list], ['rviz2'])


if __name__ == '__main__':
    unittest.main()

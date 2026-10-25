"""Three-table operation on a saved map with AMCL and a single velocity gate."""
import math
from pathlib import Path

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, GroupAction, IncludeLaunchDescription, OpaqueFunction
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node, SetRemap
from nav2_common.launch import RewrittenYaml


def _start(context):
    from ros_dd_navigation.launch_checks import assert_mode_available, validate_map_file

    def value(name):
        return LaunchConfiguration(name).perform(context)

    mode = value('mode')
    if mode not in ('slam', 'saved_map'):
        raise RuntimeError('mode must be slam or saved_map')
    map_path = ''
    if mode == 'saved_map':
        if not value('map').strip():
            raise RuntimeError(
                'Saved-map navigation requires map:=/absolute/path/to/map.yaml. '
                'First run ros2 launch ros_dd_navigation three_tables_mapping.launch.py, '
                'save the map, and stop mapping before starting the harness.')
        map_path = validate_map_file(value('map'))
    assert_mode_available('harness ' + mode, value('start_simulation').lower() in ('true', '1'))
    nav = Path(get_package_share_directory('ros_dd_navigation'))
    gazebo = Path(get_package_share_directory('ros_dd_gazebo'))
    clock = LaunchConfiguration('use_sim_time')

    def include(path, arguments):
        return IncludeLaunchDescription(PythonLaunchDescriptionSource(str(path)),
                                        launch_arguments=arguments.items())

    # AMCL initialization is opt-in: saved-map coordinates must be measured first.
    # The same file also forces Twist for Jazzy's Nav2 -> gate -> Harmonic bridge.
    rewrites = {'enable_stamped_cmd_vel': 'false'}
    if mode == 'saved_map' and value('set_initial_pose').lower() in ('true', '1'):
        for name in ('initial_x', 'initial_y', 'initial_yaw'):
            if not math.isfinite(float(value(name))):
                raise RuntimeError(f'{name} must be finite')
        rewrites.update({'amcl.ros__parameters.set_initial_pose': 'true',
                         'amcl.ros__parameters.initial_pose.x': value('initial_x'),
                         'amcl.ros__parameters.initial_pose.y': value('initial_y'),
                         'amcl.ros__parameters.initial_pose.z': '0.0',
                         'amcl.ros__parameters.initial_pose.yaw': value('initial_yaw')})
    params = RewrittenYaml(source_file=LaunchConfiguration('params_file'),
                           param_rewrites=rewrites, convert_types=True)
    actions = [
        GroupAction(actions=[include(gazebo / 'launch/three_tables.launch.py', {
            'gui': LaunchConfiguration('gui'), 'use_sim_time': clock})],
            condition=IfCondition(LaunchConfiguration('start_simulation'))),
        Node(package='slam_harness_jazzy', executable='velocity_gate',
             parameters=[{'use_sim_time': clock}], output='screen'),
    ]
    if mode == 'slam':
        cartographer = Path(get_package_share_directory('ros_dd_cartographer'))
        actions.append(GroupAction(actions=[include(
            cartographer / 'launch/ros_dd_cartograph.launch.py', {
                'configuration_basename': 'three_tables.lua',
                'use_rviz': 'false', 'use_sim_time': clock})]))
    # Remap the smoother original output name, preserving controller -> smoother.
    # Scoped remaps precede Node remaps; ROS does not recursively remap destinations.
    actions.append(GroupAction(actions=[
        SetRemap(src='/cmd_vel_smoothed', dst='/slam_harness/nav_cmd_vel'),
        include(nav / 'launch/navigation.launch.py', {
            'use_localization': 'true' if mode == 'saved_map' else 'false',
            'map': map_path, 'params_file': params, 'use_sim_time': clock,
            'use_rviz': LaunchConfiguration('use_rviz'),
            'rviz_software_rendering': LaunchConfiguration('rviz_software_rendering'),
        }),
    ]))
    return actions


def generate_launch_description():
    nav = Path(get_package_share_directory('ros_dd_navigation'))
    return LaunchDescription([
        DeclareLaunchArgument('mode', default_value='saved_map', choices=['saved_map', 'slam'],
                              description='Use a fixed saved map and AMCL for normal operation'),
        DeclareLaunchArgument('map', default_value='',
                              description='Required for saved_map: YAML created in the mapping stage'),
        DeclareLaunchArgument('params_file', default_value=str(nav / 'config/three_tables_nav2.yaml')),
        DeclareLaunchArgument('gui', default_value='true'),
        DeclareLaunchArgument('use_rviz', default_value='true'),
        DeclareLaunchArgument('rviz_software_rendering', default_value='false'),
        DeclareLaunchArgument('use_sim_time', default_value='true'),
        DeclareLaunchArgument('start_simulation', default_value='true'),
        DeclareLaunchArgument('set_initial_pose', default_value='false',
                              description='Use verified map-frame initial_x/y/yaw, otherwise set pose in RViz'),
        DeclareLaunchArgument('initial_x', default_value='0.0'),
        DeclareLaunchArgument('initial_y', default_value='0.0'),
        DeclareLaunchArgument('initial_yaw', default_value='0.0'),
        OpaqueFunction(function=_start),
    ])

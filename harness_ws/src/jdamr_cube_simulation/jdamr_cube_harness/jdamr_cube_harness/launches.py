"""JDAMR-only two-stage Gazebo mapping and saved-map harness launch graphs."""
import math
import os
import shutil
from pathlib import Path
import tempfile

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, ExecuteProcess, LogInfo
from launch.actions import OpaqueFunction, RegisterEventHandler, SetEnvironmentVariable, Shutdown
from launch.event_handlers import OnShutdown
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue
import yaml

from .launch_checks import assert_mode_available, validate_map_file
from .parameters import navigation_parameters
from .mapping_parameters import DEFAULT_SLAM_MAX_RANGE, mapping_configuration


def _value(context, name):
    return LaunchConfiguration(name).perform(context)


def _enabled(context, name):
    return _value(context, name).lower() in ('true', '1')


def _simulation(context, share):
    description = Path(get_package_share_directory('jdamr_cube_description'))
    text = (description / 'urdf/new_base_sim.urdf').read_text()
    arguments = ['gz', 'sim', '-r']
    if not _enabled(context, 'gui'):
        arguments += ['-s', '--headless-rendering']
    arguments += ['--force-version', '8', str(share / 'worlds/three_tables.world')]
    return [
        SetEnvironmentVariable('GZ_SIM_RESOURCE_PATH', os.pathsep.join([
            str(share / 'models'), str(description.parent),
            os.environ.get('GZ_SIM_RESOURCE_PATH', '')])),
        ExecuteProcess(cmd=arguments, name='jdamr_gazebo', output='screen',
                       on_exit=Shutdown(reason='JDAMR Gazebo exited')),
        Node(package='robot_state_publisher', executable='robot_state_publisher',
             name='robot_state_publisher', parameters=[{'use_sim_time': True,
                 'robot_description': ParameterValue(text, value_type=str)}], output='screen'),
        Node(package='ros_gz_sim', executable='create', arguments=[
            '-world', 'three_tables', '-name', 'jdamr_cube', '-topic', 'robot_description',
            '-x', '0', '-y', '0', '-z', '.003'], output='screen'),
        Node(package='ros_gz_bridge', executable='parameter_bridge', name='jdamr_bridge',
             parameters=[{'use_sim_time': True, 'config_file':str(share / 'config/bridge.yaml')}],
             output='screen'),
    ]


def _rviz(context, share, mode):
    if not _enabled(context, 'use_rviz'):
        return []
    return [Node(package='rviz2', executable='rviz2',
                 arguments=['-d', str(share / f'rviz/{mode}.rviz')],
                 parameters=[{'use_sim_time':True}], output='screen')]


def _mapping(context):
    assert_mode_available('mapping', True)
    share = Path(get_package_share_directory('jdamr_cube_harness'))
    cartographer = Path(get_package_share_directory('jdamr_cube_cartographer'))
    profile = _value(context, 'slam_profile')
    configuration = mapping_configuration(
        (cartographer / f'config/jdamr_cube_2d_{profile}.lua').read_text(),
        _value(context, 'slam_max_range'))
    directory = Path(tempfile.mkdtemp(prefix='jdamr_mapping_'))
    (directory / 'simulation.lua').write_text(configuration)
    def cleanup(_context):
        shutil.rmtree(directory, ignore_errors=True)
        return []
    return _simulation(context, share) + [
        RegisterEventHandler(OnShutdown(on_shutdown=[OpaqueFunction(function=cleanup)])),
        LogInfo(msg=f'JDAMR mapping: {profile} base profile, simulation SLAM range '
                    f'{_value(context, "slam_max_range")}m; sensor range 16m.'),
        Node(package='cartographer_ros', executable='cartographer_node', name='cartographer_node',
             parameters=[{'use_sim_time':True}], arguments=[
                 '-configuration_directory', str(directory),
                 '-configuration_basename', 'simulation.lua'], output='screen'),
        Node(package='cartographer_ros', executable='cartographer_occupancy_grid_node',
             name='occupancy_grid_node', parameters=[{'use_sim_time':True}],
             arguments=['-resolution', '.05', '-publish_period_sec', '1.0'], output='screen'),
    ] + _rviz(context, share, 'mapping')


def _navigation(context):
    if not _value(context, 'map').strip():
        raise RuntimeError('First create and save a JDAMR map, stop mapping, then pass map:=/path/map.yaml')
    path = validate_map_file(_value(context, 'map'))
    initial = tuple(float(_value(context, name)) for name in ('initial_x','initial_y','initial_yaw'))
    if not all(math.isfinite(v) for v in initial):
        raise RuntimeError('Initial pose must contain finite map-frame coordinates')
    assert_mode_available('saved-map harness navigation', True)
    share = Path(get_package_share_directory('jdamr_cube_harness'))
    parameters = navigation_parameters(share, path, _enabled(context, 'set_initial_pose'), initial)
    # Pass a file for nested costmap namespaces; remove it when launch stops.
    temporary = tempfile.NamedTemporaryFile(mode='w', prefix='jdamr_nav2_', suffix='.yaml', delete=False)
    yaml.safe_dump(parameters, temporary, sort_keys=False)
    temporary.close()
    from launch.actions import RegisterEventHandler, OpaqueFunction
    from launch.event_handlers import OnShutdown
    def cleanup(_context):
        Path(temporary.name).unlink(missing_ok=True)
        return []
    actions = _simulation(context, share) + [
        RegisterEventHandler(OnShutdown(on_shutdown=[OpaqueFunction(function=cleanup)])),
        Node(package='nav2_map_server', executable='map_server', name='map_server',
             parameters=[temporary.name], output='screen'),
        Node(package='nav2_amcl', executable='amcl', name='amcl',
             parameters=[temporary.name], output='screen'),
        Node(package='nav2_lifecycle_manager', executable='lifecycle_manager',
             name='lifecycle_manager_localization', parameters=[{'use_sim_time':True,
                 'autostart':True, 'node_names':['map_server','amcl']}], output='screen'),
        Node(package='jdamr_cube_harness', executable='velocity_mux',
             parameters=[{'use_sim_time':True}], output='screen'),
    ]
    servers = [
        ('nav2_collision_monitor','collision_monitor'),
        ('nav2_controller','controller_server'), ('nav2_smoother','smoother_server'),
        ('nav2_planner','planner_server'), ('nav2_behaviors','behavior_server'),
        ('nav2_velocity_smoother','velocity_smoother'), ('nav2_bt_navigator','bt_navigator'),
    ]
    for package, name in servers:
        remaps = []
        if name in ('controller_server','behavior_server'):
            remaps = [('cmd_vel','/jdamr_harness/nav_raw')]
        elif name == 'velocity_smoother':
            remaps = [('cmd_vel','/jdamr_harness/nav_raw'),
                      ('cmd_vel_smoothed','/slam_harness/nav_cmd_vel')]
        actions.append(Node(package=package, executable=name, name=name,
                            parameters=[temporary.name], remappings=remaps, output='screen'))
    actions += [
        Node(package='nav2_lifecycle_manager', executable='lifecycle_manager',
             name='lifecycle_manager_navigation', parameters=[{'use_sim_time':True,
                 'autostart':False,'node_names':[name for _,name in servers]}], output='screen'),
        Node(package='jdamr_cube_harness', executable='navigation_startup',
             parameters=[{'use_sim_time':True}], output='screen'),
    ]
    return actions + _rviz(context, share, 'navigation')


def mapping_launch():
    return LaunchDescription([
        DeclareLaunchArgument('gui',default_value='true'),
        DeclareLaunchArgument('use_rviz',default_value='true'),
        DeclareLaunchArgument('slam_profile',default_value='real',choices=['real','corridor'],
                              description='Physical JDAMR base profile with simulation range override'),
        DeclareLaunchArgument('slam_max_range', default_value=str(DEFAULT_SLAM_MAX_RANGE),
                              description='Simulation SLAM observation limit in metres: >0.28, <=16.0'),
        OpaqueFunction(function=_mapping),
    ])


def navigation_launch():
    return LaunchDescription([
        DeclareLaunchArgument('map',default_value='',description='Required: map saved by JDAMR mapping'),
        DeclareLaunchArgument('gui',default_value='true'),
        DeclareLaunchArgument('use_rviz',default_value='true'),
        DeclareLaunchArgument('set_initial_pose',default_value='false'),
        DeclareLaunchArgument('initial_x',default_value='0.0'),
        DeclareLaunchArgument('initial_y',default_value='0.0'),
        DeclareLaunchArgument('initial_yaw',default_value='0.0'),
        OpaqueFunction(function=_navigation),
    ])

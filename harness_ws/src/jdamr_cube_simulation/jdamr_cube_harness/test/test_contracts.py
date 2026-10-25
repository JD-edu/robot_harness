"""Imported physical geometry / SLAM contracts and harness arbitration regressions."""
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

import yaml
from geometry_msgs.msg import Twist
from jdamr_cube_harness.parameters import navigation_parameters
from jdamr_cube_harness.mapping_parameters import mapping_configuration
from jdamr_cube_harness.launches import mapping_launch
from jdamr_cube_harness.velocity_mux import VelocityMux
from jdamr_cube_harness import mission
from jdamr_cube_harness.launches import navigation_launch, _navigation
from launch import LaunchContext
from launch.actions import DeclareLaunchArgument

BUNDLE=Path(__file__).resolve().parents[2]
SHARE=BUNDLE/'jdamr_cube_harness'


class PhysicalContracts(unittest.TestCase):
    def test_imported_physical_sources_are_unchanged(self):
        provenance=json.loads((BUNDLE/'IMPORT_PROVENANCE.json').read_text())
        for item in provenance['unchanged_imports']:
            with self.subTest(path=item['destination']):
                actual=(BUNDLE/item['destination']).read_bytes()
                self.assertEqual(hashlib.sha256(actual).hexdigest(),item['sha256'])

    def test_simulator_preserves_all_physical_fixed_transforms_and_wheel_geometry(self):
        folder=BUNDLE/'jdamr_cube_description/urdf'
        original=ET.parse(folder/'new_base_real.urdf').getroot()
        simulation=ET.parse(folder/'new_base_sim.urdf').getroot()
        for joint in original.findall('joint'):
            other=simulation.find(f"joint[@name='{joint.get('name')}']")
            self.assertEqual(joint.attrib,other.attrib)
            for item in joint:
                self.assertEqual(item.attrib,other.find(item.tag).attrib)
        plugin=simulation.find("gazebo/plugin[@name='gz::sim::systems::DiffDrive']")
        geometry=yaml.safe_load((BUNDLE/'jdamr_cube_description/config/new_base_geometry.yaml').read_text())
        self.assertEqual(float(plugin.findtext('wheel_separation')),geometry['wheel_center_separation']['value'])
        self.assertEqual(float(plugin.findtext('wheel_radius')),geometry['wheel_radius_initial']['value'])
        self.assertEqual(plugin.findtext('child_frame_id'),'base_footprint')
        sensor=simulation.find("gazebo[@reference='laser_link']/sensor")
        self.assertEqual(sensor.findtext('gz_frame_id'),'laser_link')
        self.assertEqual(float(sensor.findtext('lidar/range/min')),.28)

    def test_physical_mapping_uses_odometry_not_legacy_sim_profile(self):
        directory=BUNDLE/'jdamr_cube_cartographer/config'
        text=(directory/'jdamr_cube_2d_real.lua').read_text()
        self.assertIn('use_odometry = true',text)
        self.assertIn('tracking_frame = "base_link"',text)
        self.assertIn('TRAJECTORY_BUILDER_2D.use_imu_data = false',text)
        self.assertIn('pose_publish_period_sec = 5e-2',text)
        self.assertIn('TRAJECTORY_BUILDER_2D.max_range = 3.5',text)

    def test_simulation_range_override_preserves_each_physical_profile(self):
        context=LaunchContext()
        for action in mapping_launch().entities:
            if isinstance(action,DeclareLaunchArgument):action.execute(context)
        self.assertEqual(context.launch_configurations['slam_max_range'],'8.0')
        for profile in ('real','corridor'):
            source=(BUNDLE/f'jdamr_cube_cartographer/config/jdamr_cube_2d_{profile}.lua').read_text()
            for distance in (8.,12.,16.,3.5):
                adapted=mapping_configuration(source,distance)
                self.assertTrue(adapted.startswith(source.rsplit('return options',1)[0]))
                self.assertTrue(adapted.endswith(f'TRAJECTORY_BUILDER_2D.max_range = {distance!r}\nreturn options\n'))
        sensor=ET.parse(BUNDLE/'jdamr_cube_description/urdf/new_base_sim.urdf').find(
            "gazebo[@reference='laser_link']/sensor")
        self.assertEqual(float(sensor.findtext('lidar/range/max')),16.)

    def test_simulation_rejects_ranges_outside_sensor_capability(self):
        for distance in ('nan','inf','-inf',0,-1,.28,16.01,'invalid'):
            with self.subTest(distance=distance), self.assertRaises(ValueError):
                mapping_configuration('return options',distance)

    def test_runtime_preserves_jdamr_footprint_controllers_and_stop_polygons(self):
        original=yaml.safe_load((SHARE/'config/upstream_new_base_nav2.yaml').read_text())
        adapted=navigation_parameters(SHARE,'/tmp/fresh_map.yaml')
        for costmap in ('local_costmap','global_costmap'):
            self.assertEqual(original[costmap][costmap]['ros__parameters']['footprint'],
                             adapted[costmap][costmap]['ros__parameters']['footprint'])
        self.assertEqual(original['controller_server']['ros__parameters']['MPPI'],
                         adapted['controller_server']['ros__parameters']['MPPI'])
        self.assertEqual(original['collision_monitor']['ros__parameters']['StopZone'],
                         adapted['collision_monitor']['ros__parameters']['StopZone'])
        self.assertEqual(adapted['collision_monitor']['ros__parameters']['cmd_vel_in_topic'],
                         '/jdamr_harness/selected_cmd_vel')
        self.assertEqual(adapted['collision_monitor']['ros__parameters']['cmd_vel_out_topic'],'/cmd_vel')
        self.assertFalse(adapted['amcl']['ros__parameters']['set_initial_pose'])
        self.assertEqual(adapted['map_server']['ros__parameters']['yaml_filename'],'/tmp/fresh_map.yaml')
        self.assertEqual(adapted['planner_server']['ros__parameters']['planner_plugins'],['GridBased'])
        self.assertIn('staging_position_checker',adapted['controller_server']['ros__parameters']['goal_checker_plugins'])

    def test_automatic_initial_pose_is_opt_in_and_has_matching_sim_clock(self):
        adapted=navigation_parameters(SHARE,'/tmp/fresh_map.yaml',True,(1.,-2.,.3))
        self.assertEqual(adapted['amcl']['ros__parameters']['initial_pose'],{'x':1.,'y':-2.,'yaw':.3,'z':0.})
        self.assertTrue(adapted['amcl']['ros__parameters']['set_initial_pose'])
        for name in ('controller_server','collision_monitor','amcl','bt_navigator'):
            self.assertTrue(adapted[name]['ros__parameters']['use_sim_time'])
            self.assertFalse(adapted[name]['ros__parameters']['enable_stamped_cmd_vel'])

    def test_map_is_required_before_any_simulator_or_ros_graph_is_started(self):
        context=LaunchContext()
        for action in navigation_launch().entities:
            if isinstance(action,DeclareLaunchArgument):action.execute(context)
        with patch('jdamr_cube_harness.launches.assert_mode_available') as check:
            with self.assertRaisesRegex(RuntimeError,'First create and save a JDAMR map'):
                _navigation(context)
            check.assert_not_called()


class HarnessAdapterTests(unittest.TestCase):
    def test_mission_injects_jdamr_locations_before_ros_args(self):
        with patch.object(mission,'harness_main',return_value=0) as run:
            self.assertEqual(mission.main(['테이블 1로 가','--ros-args','-p','use_sim_time:=true']),0)
            arguments=run.call_args.args[0]
            self.assertLess(arguments.index('--locations'),arguments.index('--ros-args'))
            self.assertIn('jdamr_cube_harness/config/locations.yaml',arguments[arguments.index('--locations')+1])

    def test_explicit_locations_remain_selected(self):
        for form in (['--locations','/tmp/mine.yaml'],['--locations=/tmp/mine.yaml']):
            with patch.object(mission,'harness_main') as run:
                mission.main(['테스트',*form,'--dry-run'])
                self.assertEqual(run.call_args.args[0],['테스트',*form,'--dry-run','--align-timeout','60'])

    def test_explicit_alignment_timeout_is_preserved(self):
        with patch.object(mission,'harness_main') as run:
            mission.main(['테이블 1','--align-timeout','17','--ros-args','-p','use_sim_time:=true'])
            argv=run.call_args.args[0]
            self.assertEqual(argv.count('--align-timeout'),1)
            self.assertEqual(argv[argv.index('--align-timeout')+1],'17')

    def test_mux_switch_discards_stale_commands_and_stops(self):
        sent=[]
        probe=NS(fine=False,commands={'nav':object()},output=NS(publish=sent.append))
        response=VelocityMux.set_mode(probe,NS(data=True),NS(success=False))
        self.assertTrue(response.success)
        self.assertTrue(probe.fine)
        self.assertEqual(probe.commands,{})
        self.assertEqual(sent[-1].linear.x,0.)

    def test_mux_watchdog_invalid_input_and_physical_speed_limits(self):
        for stamp,linear,yaw,expected in ((9.9,.5,1.,(.12,.3)),(9.9,-.5,-1.,(-.08,-.3)),
                                          (9.,.1,.2,(0.,0.)),(9.9,float('nan'),.2,(0.,0.))):
            command=Twist();command.linear.x=linear;command.angular.z=yaw;sent=[]
            probe=NS(fine=False,commands={'nav':(stamp,command)},output=NS(publish=sent.append))
            with patch('jdamr_cube_harness.velocity_mux.time.monotonic',return_value=10.):
                VelocityMux.tick(probe)
            self.assertEqual((sent[-1].linear.x,sent[-1].angular.z),expected)


if __name__=='__main__':unittest.main()

from glob import glob
from setuptools import setup

setup(
    name='slam_harness_jazzy', version='0.2.0',
    packages=['SLAM_harness_jazzy'], package_dir={'SLAM_harness_jazzy': '.'},
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/slam_harness_jazzy']),
        ('share/slam_harness_jazzy', ['package.xml']),
        ('share/slam_harness_jazzy/config', glob('config/*.yaml')),
        ('share/slam_harness_jazzy/launch', glob('launch/*.launch.py')),
    ],
    install_requires=['setuptools', 'PyYAML'],
    entry_points={'console_scripts': [
        'mission = SLAM_harness_jazzy.main:main',
        'velocity_gate = SLAM_harness_jazzy.velocity_gate:main',
    ]},
    maintainer='jdedu', maintainer_email='jdedu@example.com',
    description='Jazzy ros_dd three-table SLAM mission harness', license='Apache-2.0',
)

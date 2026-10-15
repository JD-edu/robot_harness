from setuptools import setup

setup(
    name='slam_harness', version='0.1.0',
    packages=['slam_harness'], package_dir={'slam_harness': '.'},
    data_files=[('share/ament_index/resource_index/packages', ['resource/slam_harness']),
                ('share/slam_harness', ['package.xml']),
                ('share/slam_harness/config', ['config/locations.yaml'])],
    install_requires=['setuptools', 'PyYAML'],
    entry_points={'console_scripts': ['mission = slam_harness.main:main', 'velocity_gate = slam_harness.velocity_gate:main']},
    maintainer='robo', maintainer_email='robo@example.com', description='Semantic Nav2 mission harness', license='Apache-2.0')

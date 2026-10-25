from pathlib import Path
from setuptools import setup

name = 'jdamr_cube_description'
assets = []
for folder in ('launch', 'config', 'urdf', 'worlds', 'models', 'rviz', 'behavior_trees'):
    for path in sorted(Path(folder).rglob('*')):
        if path.is_file() and '__pycache__' not in path.parts:
            assets.append(('share/' + name + '/' + str(path.parent), [str(path)]))
setup(name=name, version='0.1.0', packages=[name],
      data_files=[('share/ament_index/resource_index/packages', ['resource/' + name]),
                  ('share/' + name, ['package.xml'])] + assets,
      install_requires=['setuptools', 'PyYAML'],
      entry_points={'console_scripts': []},
      maintainer='jdedu', maintainer_email='jdedu@example.com',
      description='JDAMR Cube three-table simulation adapted from the local physical robot source',
      license='LicenseRef-Upstream-Unspecified')

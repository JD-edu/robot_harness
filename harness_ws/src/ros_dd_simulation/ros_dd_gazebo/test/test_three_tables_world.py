"""Validate obstacle geometry and resources in the migrated table world."""
from pathlib import Path
import xml.etree.ElementTree as ET


WORLD = Path(__file__).resolve().parents[1] / 'worlds' / 'three_tables.world'


def test_tables_are_detectable_at_laser_height():
    """Keep the original poses and solid collisions for all three tables."""
    world = ET.parse(WORLD).find('world')
    assert world.attrib['name'] == 'three_tables'
    expected = {'table_1': (2, 1.5), 'table_2': (2, -1.5), 'table_3': (-2, 1.5)}
    tables = [m for m in world.findall('model') if m.attrib['name'].startswith('table_')]
    assert len(tables) == 3
    for table in tables:
        pose = list(map(float, table.findtext('pose').split()))
        assert tuple(pose[:2]) == expected[table.attrib['name']]
        size = list(map(float, table.findtext('link/collision/geometry/box/size').split()))
        assert size == [1.2, 0.8, 0.75]
        assert pose[2] - size[2] / 2 == 0
        assert pose[2] + size[2] / 2 > 0.235
        assert table.findtext('static') == 'true'


def test_world_has_walls_and_native_harmonic_systems():
    """The world runs without Classic's ground/sun model database."""
    world = ET.parse(WORLD).find('world')
    assert not world.findall('include')
    models = {m.attrib['name'] for m in world.findall('model')}
    assert models >= {'ground_plane', 'north', 'south', 'east', 'west'}
    systems = {p.attrib['name'] for p in world.findall('plugin')}
    for name in ('Physics', 'UserCommands', 'SceneBroadcaster', 'Sensors', 'Imu'):
        assert f'gz::sim::systems::{name}' in systems


def test_table_identities_are_distinct_and_visual_only():
    """Keep the saved-map obstacles while adding visible table identities."""
    world = ET.parse(WORLD).find('world')
    colors = set()
    for number in (1, 2, 3):
        table = world.find(f"model[@name='table_{number}']")
        colors.add(table.findtext('link/visual/material/diffuse'))
        identity = table.find("link[@name='identity_label']")
        assert identity is not None
        assert not identity.findall('collision')
        assert len(table.findall('.//collision')) == 1
        label_height = float(identity.findtext('pose').split()[2])
        panel_height = float(identity.findtext('visual/geometry/box/size').split()[2])
        assert .375 + label_height - panel_height / 2 > .75
        top = table.find("link/visual[@name='table_number_top']")
        assert .375 + float(top.findtext('pose').split()[2]) - .004 > .75
        uris = [v.findtext('geometry/mesh/uri') for v in identity.findall('visual')
                if v.find('geometry/mesh') is not None]
        uris.append(top.findtext('geometry/mesh/uri'))
        assert len(uris) == 3
        for uri in uris:
            assert uri == f'model://table_labels/meshes/number_{number}.dae'
            assert (WORLD.parents[1] / 'models' / uri.removeprefix('model://')).is_file()
    assert len(colors) == 3

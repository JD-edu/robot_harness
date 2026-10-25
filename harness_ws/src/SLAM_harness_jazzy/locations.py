"""1. locations.yaml을 읽고 테이블 좌표를 준비합니다. ROS 없이 읽을 수 있습니다."""
from dataclasses import dataclass
import math
from pathlib import Path

import yaml


# dataclass는 아래 변수들을 가진 간단한 데이터 보관용 클래스를 만들어 줍니다.
# Pose(1.0, 2.0, 0.0)을 만들면 pose.x, pose.y, pose.yaw로 읽을 수 있습니다.
@dataclass(frozen=True)
class Pose:
    x: float
    y: float
    yaw: float

    @classmethod
    def parse(cls, data):
        """YAML의 {x: ..., y: ..., yaw: ...}를 Pose로 변환합니다."""
        if not isinstance(data, dict):
            raise ValueError('pose must contain exactly x, y, yaw')
        if set(data.keys()) != {'x', 'y', 'yaw'}:
            raise ValueError('pose must contain exactly x, y, yaw')

        for value in data.values():
            # True/False는 좌표로 받지 않도록 type으로 숫자를 확인합니다.
            if type(value) not in (int, float):
                raise ValueError('pose coordinates must be finite numbers')
            if not math.isfinite(value):
                raise ValueError('pose coordinates must be finite numbers')

        return cls(x=data['x'], y=data['y'], yaw=data['yaw'])


@dataclass(frozen=True)
class Landmark:
    approach: Pose
    align: Pose
    retreat: Pose
    target_point: Pose


def load_registry(path):
    """파일을 한 번 읽어 {테이블 이름: Landmark} 사전을 만듭니다."""
    text = Path(path).read_text()
    data = yaml.safe_load(text)

    if not isinstance(data, dict):
        raise ValueError('registry requires map frame and landmarks')
    if set(data.keys()) != {'frame_id', 'landmarks'}:
        raise ValueError('registry requires map frame and landmarks')
    if data['frame_id'] != 'map':
        raise ValueError('registry requires map frame and landmarks')
    if not isinstance(data['landmarks'], dict):
        raise ValueError('landmarks must be a dictionary')

    registry = {}
    for name, coordinates in data['landmarks'].items():
        if not isinstance(name, str) or not isinstance(coordinates, dict):
            raise ValueError('invalid landmark entry')
        if set(coordinates.keys()) != {'approach', 'align', 'retreat', 'target_point'}:
            raise ValueError('invalid landmark entry')

        registry[name] = Landmark(
            approach=Pose.parse(coordinates['approach']),
            align=Pose.parse(coordinates['align']),
            retreat=Pose.parse(coordinates['retreat']),
            target_point=Pose.parse(coordinates['target_point']),
        )

    if not registry:
        raise ValueError('registry is empty')
    return registry

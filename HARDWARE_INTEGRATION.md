# Stage 10~11 실제 하드웨어 연결

현재 저장소는 장비가 없어도 검증할 수 있도록 camera/gripper는 loopback, arm은
dry-run이 기본값입니다. 포트나 통신 프로토콜을 추측해 실제 모터를 움직이지 않습니다.

## 교체할 인터페이스

실제 camera는 다음 메서드를 구현합니다.

```python
class MyCamera:
    def read(self):
        return {"ok": True, "timestamp": ..., "rgb": ..., "depth": ...}
```

실제 gripper는 `command(position, max_force)`와 `state()`를 구현합니다. 실제 arm
driver는 아래 세 메서드를 구현합니다.

```python
class MySO101Driver:
    def read_joints(self): ...
    def write_joints(self, positions): ...
    def stop(self): ...
```

그 다음 명시적으로 주입합니다.

```python
from stage10_hil.devices import HILSession
from stage11_real_robot.integration import RealRobotHarness

harness = RealRobotHarness(
    arm_driver=MySO101Driver(...),
    hil=HILSession(camera=MyCamera(...), gripper=MyGripper(...)),
)
assert harness.start(operator_confirmed=True)["ok"]
```

## 실제 장비 투입 전 체크

1. 로봇을 작업물과 분리하고 낮은 torque/current limit로 통신만 확인합니다.
2. `read_joints()` 단위가 radian이고 관절 순서가 정책 출력과 같은지 확인합니다.
3. `stop()`이 통신 오류 중에도 동작하는지 확인합니다.
4. `SafetySupervisor`의 joint limit와 `max_delta`를 장비 사양에 맞춥니다.
5. camera timestamp 지연과 depth 단위(m)를 검증합니다.
6. 물리 E-stop과 작업자 감시 하에서 한 관절씩 시험합니다.

실제 장비용 구현에 필요한 정보는 SO101의 제어 SDK/프로토콜, 장치 경로, 관절 순서,
캘리브레이션 값, gripper와 camera 모델입니다.

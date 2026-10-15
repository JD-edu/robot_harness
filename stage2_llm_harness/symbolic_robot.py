"""실제 로봇 대신 상태만 바뀌는 간단한 가상 로봇입니다."""


class ObjectState:
    """컵이나 페트병 같은 물체 하나의 상태입니다."""

    def __init__(self, name, kind, location):
        self.name = name
        self.kind = kind
        self.location = location
        self.held_by = None
        self.cap_open = False


class SymbolicWorld:
    """로봇 주변에 있는 물체들을 보관합니다."""

    def __init__(self):
        self.objects = {}

    def add(self, obj):
        self.objects[obj.name] = obj

    def get(self, name):
        if name not in self.objects:
            raise KeyError("unknown object: " + name)
        return self.objects[name]

    def snapshot(self):
        result = {}

        for name, obj in self.objects.items():
            result[name] = {
                "name": obj.name,
                "kind": obj.kind,
                "location": obj.location,
                "held_by": obj.held_by,
                "cap_open": obj.cap_open,
            }

        return result


class SymbolicRobot:
    """왼손과 오른손에 무엇을 들고 있는지 기억합니다."""

    def __init__(self):
        self.left_hand = None
        self.right_hand = None

    def held(self, arm):
        if arm == "left":
            return self.left_hand
        if arm == "right":
            return self.right_hand
        raise ValueError("arm must be left or right")

    def set_held(self, arm, object_name):
        if arm == "left":
            self.left_hand = object_name
        elif arm == "right":
            self.right_hand = object_name
        else:
            raise ValueError("arm must be left or right")

    def snapshot(self):
        return {
            "left_hand": self.left_hand,
            "right_hand": self.right_hand,
        }

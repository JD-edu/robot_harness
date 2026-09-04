class ObjectState:
    def __init__(self, name, kind, location, held_by=None, cap_open=False):
        self.name = name
        self.kind = kind
        self.location = location
        self.held_by = held_by
        self.cap_open = cap_open


class SymbolicWorld:
    def __init__(self):
        self.objects = {}

    def add(self, obj):
        self.objects[obj.name] = obj

    def get(self, name):
        if name not in self.objects:
            raise KeyError("unknown object: {}".format(name))
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
    def __init__(self):
        self.left_hand = None
        self.right_hand = None

    def held(self, arm):
        if arm == "left":
            return self.left_hand
        if arm == "right":
            return self.right_hand
        raise ValueError("arm must be left or right")

    def set_held(self, arm, obj):
        if arm == "left":
            self.left_hand = obj
        elif arm == "right":
            self.right_hand = obj
        else:
            raise ValueError("arm must be left or right")

    def __repr__(self):
        return "SymbolicRobot(left_hand={!r}, right_hand={!r})".format(
            self.left_hand, self.right_hand
        )

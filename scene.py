"""Core scene data structures and generation logic."""

from __future__ import annotations
import threading
from collections import deque
import numpy as np
import pyqtgraph.opengl as gl
from pydantic import BaseModel, field_validator


# ====================================================================== #
#  Primitives
# ====================================================================== #

def create_box():
    """Create a simple 1x1x1 cube."""
    vertexes = np.array([
        [ 0.5,  0.5,  0.5], [-0.5,  0.5,  0.5], [-0.5, -0.5,  0.5], [ 0.5, -0.5,  0.5],
        [ 0.5,  0.5, -0.5], [-0.5,  0.5, -0.5], [-0.5, -0.5, -0.5], [ 0.5, -0.5, -0.5]
    ], dtype=np.float32)
    faces = np.array([
        [0, 1, 2], [0, 2, 3], [7, 6, 5], [7, 5, 4], [4, 5, 1], [4, 1, 0],
        [3, 2, 6], [3, 6, 7], [0, 3, 7], [0, 7, 4], [5, 6, 2], [5, 2, 1]
    ], dtype=np.uint32)
    md = gl.MeshData(vertexes=vertexes, faces=faces)
    return md.vertexes(), md.vertexNormals(), md.faces()

def create_cylinder():
    """Create a cylinder with properly shaded top and bottom caps."""
    cols = 24
    radius, half_l = 0.5, 0.5
    verts, normals, faces = [], [], []
    angles = np.linspace(0, 2*np.pi, cols, endpoint=False)
    cos_a, sin_a = np.cos(angles), np.sin(angles)
    
    # 1. Sides
    for i in range(cols):
        verts.extend([[radius*cos_a[i], radius*sin_a[i], -half_l], [radius*cos_a[i], radius*sin_a[i], half_l]])
        normals.extend([[cos_a[i], sin_a[i], 0.0], [cos_a[i], sin_a[i], 0.0]])
    for i in range(cols):
        n = (i + 1) % cols
        faces.extend([[2*i, 2*n, 2*i+1], [2*i+1, 2*n, 2*n+1]])
        
    # 2. Top cap
    t_idx = len(verts)
    verts.append([0.0, 0.0, half_l])
    normals.append([0.0, 0.0, 1.0])
    for i in range(cols):
        verts.append([radius*cos_a[i], radius*sin_a[i], half_l])
        normals.append([0.0, 0.0, 1.0])
    for i in range(cols):
        faces.append([t_idx, t_idx + 1 + i, t_idx + 1 + ((i + 1) % cols)])
        
    # 3. Bottom cap
    b_idx = len(verts)
    verts.append([0.0, 0.0, -half_l])
    normals.append([0.0, 0.0, -1.0])
    for i in range(cols):
        verts.append([radius*cos_a[i], radius*sin_a[i], -half_l])
        normals.append([0.0, 0.0, -1.0])
    for i in range(cols):
        faces.append([b_idx, b_idx + 1 + ((i + 1) % cols), b_idx + 1 + i])

    return np.array(verts, dtype=np.float32), np.array(normals, dtype=np.float32), np.array(faces, dtype=np.uint32)

def create_sphere():
    """Create a sphere using pyqtgraph's built-in generator."""
    md = gl.MeshData.sphere(rows=20, cols=20, radius=0.5)
    return md.vertexes(), md.vertexNormals(), md.faces()

def create_cone():
    """Create a cone with a properly shaded bottom cap."""
    cols = 24
    radius, half_l = 0.5, 0.5
    verts, normals, faces = [], [], []
    angles = np.linspace(0, 2*np.pi, cols, endpoint=False)
    cos_a, sin_a = np.cos(angles), np.sin(angles)
    
    n_len = np.sqrt(1.0**2 + radius**2)
    nr, nz = 1.0 / n_len, radius / n_len
    
    # 1. Sides
    for i in range(cols):
        verts.append([0.0, 0.0, half_l])
        normals.append([nr*cos_a[i], nr*sin_a[i], nz])
        verts.append([radius*cos_a[i], radius*sin_a[i], -half_l])
        normals.append([nr*cos_a[i], nr*sin_a[i], nz])
    for i in range(cols):
        faces.append([2*i, 2*i+1, 2*((i + 1) % cols)+1])
        
    # 2. Bottom cap
    b_idx = len(verts)
    verts.append([0.0, 0.0, -half_l])
    normals.append([0.0, 0.0, -1.0])
    for i in range(cols):
        verts.append([radius*cos_a[i], radius*sin_a[i], -half_l])
        normals.append([0.0, 0.0, -1.0])
    for i in range(cols):
        faces.append([b_idx, b_idx + 1 + ((i + 1) % cols), b_idx + 1 + i])

    return np.array(verts, dtype=np.float32), np.array(normals, dtype=np.float32), np.array(faces, dtype=np.uint32)

PRIMITIVE_FACTORIES = {
    "box": create_box,
    "cylinder": create_cylinder,
    "sphere": create_sphere,
    "cone": create_cone,
}


# ====================================================================== #
#  Base Object
# ====================================================================== #

class ObjectData(BaseModel):
    """Serializable data for a scene object."""
    name: str = "Object"
    color: list[float] = [0.7, 0.7, 0.85]
    position: list[float] = [0.0, 0.0, 0.0]
    rotation: list[float] = [0.0, 0.0, 0.0]
    scale: list[float] = [1.0, 1.0, 1.0]

    @field_validator("color")
    @classmethod
    def validate_color(cls, v):
        return [max(0.0, min(1.0, c)) for c in v[:3]]


class BaseObject:
    """Scene object with mesh data and material properties."""
    next_id = 0

    def __init__(self, name: str = "", color: tuple[float, float, float] | None = None):
        self._id = BaseObject.next_id
        BaseObject.next_id += 1

        self.name = name or f"Object_{self._id}"
        self.position = np.array([0.0, 0.0, 0.0], dtype=np.float32)
        self.rotation_euler = np.array([0.0, 0.0, 0.0], dtype=np.float32)
        self.scale = np.array([1.0, 1.0, 1.0], dtype=np.float32)
        self.parent = None

        self.mesh = None
        self.color = np.array(color if color else [0.7, 0.7, 0.85], dtype=np.float32)
        self.selected = False
        self.layer_id: int | None = None    # Set by Document.add_object

    @property
    def id(self) -> int:
        return self._id

    def set_mesh(self, mesh):
        self.mesh = mesh

    def set_color(self, r: float, g: float, b: float):
        self.color[0] = max(0.0, min(1.0, r))
        self.color[1] = max(0.0, min(1.0, g))
        self.color[2] = max(0.0, min(1.0, b))

    def to_data(self) -> ObjectData:
        return ObjectData(
            name=self.name,
            color=[float(c) for c in self.color],
            position=[float(p) for p in self.position],
            rotation=[float(r) for r in np.degrees(self.rotation_euler)],
            scale=[float(s) for s in self.scale],
        )

    def from_data(self, data: ObjectData):
        self.name = data.name
        self.color = np.array(data.color[:3], dtype=np.float32)
        self.position = np.array(data.position[:3], dtype=np.float32)
        rot_rad = np.radians(data.rotation[:3])
        self.rotation_euler[0] = rot_rad[1]
        self.rotation_euler[1] = rot_rad[0]
        self.rotation_euler[2] = rot_rad[2]
        if data.scale:
            self.scale = np.array(data.scale[:3], dtype=np.float32)

    def delete(self):
        if self.parent is not None:
            self.parent.remove_child(self)


def create_object(name: str, mesh_data_factory, color: tuple | None = None) -> BaseObject:
    """Factory function to create a scene object."""
    obj = BaseObject(name=name, color=color)
    positions, normals, indices = mesh_data_factory()
    # (Removed dynamic import of Mesh as it's no longer used by GLViewWidget, which directly takes raw vertices)
    return obj


# ====================================================================== #
#  Layer
# ====================================================================== #

class Layer:
    """A render group with z-order, visibility and lock state.

    Layers are stored in Document._layers as an ordered list where
    index 0 is the *backmost* layer and index -1 is the *frontmost*.
    Inside a layer, _object_ids is also order-significant: [0] = back,
    [-1] = front. The flat render order is just the concatenation of
    every visible layer's _object_ids, back-to-front.
    """
    next_id = 0

    def __init__(self, name: str = "Layer"):
        self._id = Layer.next_id
        Layer.next_id += 1
        self.name = name
        self.visible = True
        self.locked = False
        self._object_ids: list[int] = []   # Order: [0]=back, [-1]=front

    @property
    def id(self) -> int:
        return self._id


# ====================================================================== #
#  Document Singleton
# ====================================================================== #

class Document:
    """Singleton document managing the active scene."""
    _instance: Document | None = None
    _lock = threading.Lock()

    def __init__(self):
        self._objects: list[BaseObject] = []
        self._selected_ids: set[int] = set()
        self._undo_stack: deque = deque()
        self._redo_stack: deque = deque()
        self._layers: list[Layer] = []
        self._active_layer_id: int | None = None
        self._ensure_default_layer()

    # -- Layer management ------------------------------------------------ #

    def _ensure_default_layer(self):
        if not self._layers:
            L = Layer(name="Layer 0")
            self._layers.append(L)
            self._active_layer_id = L.id

    def get_layers(self) -> list[Layer]:
        """Return layers ordered back→front."""
        return list(self._layers)

    def get_layer(self, layer_id: int) -> Layer | None:
        for L in self._layers:
            if L.id == layer_id:
                return L
        return None

    def create_layer(self, name: str | None = None) -> Layer:
        """Create a new layer above all existing ones (frontmost)."""
        if name is None:
            name = f"Layer {len(self._layers)}"
        L = Layer(name=name)
        self._layers.append(L)
        self._active_layer_id = L.id
        return L

    def delete_layer(self, layer_id: int) -> bool:
        """Delete a layer; its objects are moved to the layer below
        (or above if removing the bottom). Returns False if last layer."""
        if len(self._layers) <= 1:
            return False
        L = self.get_layer(layer_id)
        if L is None:
            return False
        idx = self._layers.index(L)
        target = self._layers[idx - 1] if idx > 0 else self._layers[idx + 1]
        # Move objects to target layer (append to its front)
        for oid in L._object_ids:
            obj = self.get_object_by_id(oid)
            if obj is not None:
                obj.layer_id = target.id
            target._object_ids.append(oid)
        self._layers.remove(L)
        if self._active_layer_id == layer_id:
            self._active_layer_id = self._layers[-1].id
        return True

    def get_active_layer(self) -> Layer:
        L = self.get_layer(self._active_layer_id) if self._active_layer_id is not None else None
        return L or self._layers[-1]

    def set_active_layer(self, layer_id: int) -> None:
        if self.get_layer(layer_id):
            self._active_layer_id = layer_id

    def move_layer_up(self, layer_id: int) -> bool:
        """Push layer one step toward front."""
        L = self.get_layer(layer_id)
        if L is None: return False
        i = self._layers.index(L)
        if i >= len(self._layers) - 1: return False
        self._layers[i], self._layers[i + 1] = self._layers[i + 1], self._layers[i]
        return True

    def move_layer_down(self, layer_id: int) -> bool:
        L = self.get_layer(layer_id)
        if L is None: return False
        i = self._layers.index(L)
        if i <= 0: return False
        self._layers[i], self._layers[i - 1] = self._layers[i - 1], self._layers[i]
        return True

    def _find_layer_of(self, obj_id: int) -> Layer | None:
        for L in self._layers:
            if obj_id in L._object_ids:
                return L
        return None

    # -- Z-order operations inside a layer ------------------------------- #

    def bring_to_front(self, obj_id: int) -> bool:
        L = self._find_layer_of(obj_id)
        if L is None or obj_id not in L._object_ids: return False
        L._object_ids.remove(obj_id)
        L._object_ids.append(obj_id)
        return True

    def send_to_back(self, obj_id: int) -> bool:
        L = self._find_layer_of(obj_id)
        if L is None or obj_id not in L._object_ids: return False
        L._object_ids.remove(obj_id)
        L._object_ids.insert(0, obj_id)
        return True

    def bring_forward(self, obj_id: int) -> bool:
        L = self._find_layer_of(obj_id)
        if L is None or obj_id not in L._object_ids: return False
        i = L._object_ids.index(obj_id)
        if i >= len(L._object_ids) - 1: return False
        L._object_ids[i], L._object_ids[i + 1] = L._object_ids[i + 1], L._object_ids[i]
        return True

    def send_backward(self, obj_id: int) -> bool:
        L = self._find_layer_of(obj_id)
        if L is None or obj_id not in L._object_ids: return False
        i = L._object_ids.index(obj_id)
        if i <= 0: return False
        L._object_ids[i], L._object_ids[i - 1] = L._object_ids[i - 1], L._object_ids[i]
        return True

    def move_object_to_layer(self, obj_id: int, layer_id: int) -> bool:
        target = self.get_layer(layer_id)
        if target is None: return False
        cur = self._find_layer_of(obj_id)
        if cur is None: return False
        if cur is target: return True
        cur._object_ids.remove(obj_id)
        target._object_ids.append(obj_id)
        obj = self.get_object_by_id(obj_id)
        if obj is not None:
            obj.layer_id = target.id
        return True

    def get_render_order(self) -> list[int]:
        """Flat list of object IDs in back→front render order
        (hidden layers excluded)."""
        out: list[int] = []
        for L in self._layers:
            if not L.visible:
                continue
            out.extend(L._object_ids)
        return out

    def get_object_render_state(self, obj_id: int) -> tuple[bool, bool]:
        """Return (visible, locked) for the object based on its layer.
        If the object has no layer, defaults to (True, False)."""
        L = self._find_layer_of(obj_id)
        if L is None:
            return True, False
        return L.visible, L.locked

    @classmethod
    def instance(cls) -> Document | None:
        return cls._instance

    @classmethod
    def create_instance(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    @classmethod
    def destroy_instance(cls):
        with cls._lock:
            cls._instance = None

    def add_object(self, obj: BaseObject) -> None:
        self._objects.append(obj)
        self._selected_ids.add(obj.id)
        obj.parent = self
        # New object joins the active layer at the front (topmost)
        layer = self.get_active_layer()
        obj.layer_id = layer.id
        if obj.id not in layer._object_ids:
            layer._object_ids.append(obj.id)

    def remove_selected(self):
        ids_to_remove = list(self._selected_ids)
        for obj in self._objects[:]:
            if obj.id in ids_to_remove:
                if obj.parent and hasattr(obj.parent, 'remove_child'):
                    obj.parent.remove_child(obj)
                elif obj in self._objects:
                    self._objects.remove(obj)
        # Also purge from layer order lists
        for L in self._layers:
            L._object_ids = [i for i in L._object_ids if i not in ids_to_remove]

    def get_object_by_id(self, object_id: int) -> BaseObject | None:
        for obj in self._objects:
            if obj.id == object_id:
                return obj
        return None

    def deselect_all(self):
        for obj in self._objects:
            obj.selected = False
        self._selected_ids.clear()

    @property
    def selected_ids(self) -> set[int]:
        return self._selected_ids.copy()

    @selected_ids.setter
    def selected_ids(self, value):
        for obj in self._objects:
            obj.selected = obj.id in value
        self._selected_ids = value

    def get_visible_objects_sorted(self) -> list[dict]:
        return [{"object": obj} for obj in self._objects]

    def get_all_objects(self) -> list[BaseObject]:
        return list(self._objects)

    def push_command(self, command):
        self._undo_stack.append(command)
        while self._redo_stack:
            self._redo_stack.popleft()

    def undo(self):
        if not self._undo_stack:
            return False
        cmd = self._undo_stack.pop()
        cmd.undo()
        self._redo_stack.append(cmd)
        return True

    def redo(self):
        if not self._redo_stack:
            return False
        cmd = self._redo_stack.pop()
        cmd.redo()
        self._undo_stack.append(cmd)
        return True

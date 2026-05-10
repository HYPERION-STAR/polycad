"""OpenGL widget for 3D rendering using pyqtgraph GLViewWidget.

pyqtgraph provides a robust QOpenGLWidget-based viewport with built-in camera
controls, lighting setup, and mesh rendering — solving all Qt6 OpenGL issues.

Includes:
  - Move gizmo (3 colored axis arrows) for selected objects
  - Click-to-select via screen-space projection picking
  - Drag-to-move along constrained axes
"""

import math
import numpy as np
from PySide6.QtWidgets import QWidget, QVBoxLayout
from PySide6.QtCore import Qt, Signal, QEvent
from PySide6.QtGui import QVector4D
import pyqtgraph.opengl as gl


# ====================================================================== #
#  Move Gizmo — 3 axis arrows attached to the selected object
# ====================================================================== #

class MoveGizmo:
    """Manages 3 colored axis arrows for translating objects.

    Each axis arrow is a thick GLLinePlotItem that can be picked
    and dragged to move the selected object along that axis.
    """

    AXIS_COLORS = {
        'x': (1.0, 0.30, 0.30, 1.0),  # Red
        'y': (0.30, 1.00, 0.40, 1.0),  # Green
        'z': (0.30, 0.55, 1.00, 1.0),  # Blue
    }
    AXIS_HIGHLIGHT = {
        'x': (1.0, 0.55, 0.55, 1.0),
        'y': (0.55, 1.00, 0.65, 1.0),
        'z': (0.55, 0.75, 1.00, 1.0),
    }
    AXIS_DIRS = {
        'x': np.array([1, 0, 0], dtype=np.float32),
        'y': np.array([0, 1, 0], dtype=np.float32),
        'z': np.array([0, 0, 1], dtype=np.float32),
    }

    def __init__(self, gl_view):
        self._gl_view = gl_view
        self._visible = False
        self._position = np.array([0, 0, 0], dtype=np.float32)
        self._shaft_length = 2.0
        self._shafts = {}   # 'x'|'y'|'z' -> GLLinePlotItem
        self._create_items()
        self.hide()

    def _create_items(self):
        for axis in ('x', 'y', 'z'):
            color = self.AXIS_COLORS[axis]
            shaft = gl.GLLinePlotItem(
                pos=np.array([[0, 0, 0], [0, 0, 0]], dtype=np.float32),
                color=color,
                width=4.0,
                antialias=True,
            )
            shaft._gizmo_axis = axis  # Tag for picking
            self._gl_view.addItem(shaft)
            self._shafts[axis] = shaft

    def show_at(self, position):
        """Show the gizmo at the given world position."""
        self._position = np.array(position, dtype=np.float32)
        self._visible = True
        self._update_positions()
        for shaft in self._shafts.values():
            shaft.setVisible(True)

    def hide(self):
        """Hide all gizmo elements."""
        self._visible = False
        for shaft in self._shafts.values():
            shaft.setVisible(False)

    def highlight_axis(self, axis):
        """Highlight a specific axis (or None to reset all)."""
        for a, shaft in self._shafts.items():
            if a == axis:
                shaft.setData(color=self.AXIS_HIGHLIGHT[a])
                shaft.setData(width=6.0)
            else:
                shaft.setData(color=self.AXIS_COLORS[a])
                shaft.setData(width=4.0)

    def _update_positions(self):
        p = self._position
        for axis, shaft in self._shafts.items():
            d = self.AXIS_DIRS[axis]
            end = p + d * self._shaft_length
            shaft.setData(pos=np.array([p, end], dtype=np.float32))

    @property
    def visible(self):
        return self._visible

    @property
    def position(self):
        return self._position.copy()


# ====================================================================== #
#  OpenGL Widget
# ====================================================================== #

class OpenGLWidget(QWidget):
    """pyqtgraph GLViewWidget wrapper with click-to-select and move gizmo."""

    # Emitted when user clicks an object or background in the viewport
    viewport_object_selected = Signal(object)   # BaseObject or None
    # Emitted when user drags the gizmo and moves an object
    viewport_object_moved = Signal(object)      # BaseObject that was moved

    def __init__(self):
        super().__init__()
        self._objects = []  # Track all mesh items with their transforms

        # Gizmo / interaction state
        self._selected_obj = None     # Currently selected BaseObject
        self._dragging_axis = None    # 'x', 'y', 'z' or None
        self._drag_last_mouse = None  # (x, y) screen pos
        self._click_consumed = False  # Prevent camera orbit on object click

        # Use pyqtgraph's built-in GL view widget
        self._gl_view = gl.GLViewWidget()
        self._gl_view.setWindowTitle("PolyCAD 3D Viewport")

        # Configure camera defaults
        self._gl_view.setCameraPosition(
            distance=20.0,
            elevation=30.0,
            azimuth=-45.0,
        )
        self._gl_view.setBackgroundColor(38, 46, 56)

        # Reference grid
        grid = gl.GLGridItem()
        grid.setSize(10, 10)
        grid.setSpacing(1, 1)
        grid.setColor((255, 255, 255, 40))
        self._gl_view.addItem(grid)

        # XYZ axis lines at origin
        axis_length = 5.0
        axis_width = 2.5
        for direction, color in [
            ([axis_length, 0, 0], (1.0, 0.35, 0.35, 1.0)),
            ([0, axis_length, 0], (0.35, 1.0, 0.45, 1.0)),
            ([0, 0, axis_length], (0.35, 0.55, 1.0, 1.0)),
        ]:
            line = gl.GLLinePlotItem(
                pos=np.array([[0, 0, 0], direction], dtype=np.float32),
                color=color, width=axis_width, antialias=True,
            )
            self._gl_view.addItem(line)
        # Negative axis lines (faded)
        for direction, color in [
            ([-axis_length, 0, 0], (1.0, 0.35, 0.35, 0.2)),
            ([0, -axis_length, 0], (0.35, 1.0, 0.45, 0.2)),
            ([0, 0, -axis_length], (0.35, 0.55, 1.0, 0.2)),
        ]:
            line = gl.GLLinePlotItem(
                pos=np.array([[0, 0, 0], direction], dtype=np.float32),
                color=color, width=1.0, antialias=True,
            )
            self._gl_view.addItem(line)

        # Create the move gizmo (hidden initially)
        self._gizmo = MoveGizmo(self._gl_view)

        # Install event filter to intercept mouse events on the GL view
        self._gl_view.installEventFilter(self)

        # Layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._gl_view)

    # ------------------------------------------------------------------ #
    #  Mouse event interception
    # ------------------------------------------------------------------ #

    def eventFilter(self, watched, event):
        """Intercept mouse events on the GLViewWidget for picking/gizmo."""
        if watched is not self._gl_view:
            return super().eventFilter(watched, event)

        etype = event.type()

        if etype == QEvent.Type.MouseButtonPress:
            if event.button() == Qt.MouseButton.LeftButton:
                return self._on_left_press(event)

        elif etype == QEvent.Type.MouseMove:
            if self._dragging_axis is not None:
                return self._on_drag_move(event)

        elif etype == QEvent.Type.MouseButtonRelease:
            if event.button() == Qt.MouseButton.LeftButton:
                if self._dragging_axis is not None:
                    self._dragging_axis = None
                    self._drag_last_mouse = None
                    self._gizmo.highlight_axis(None)
                    return True

        return super().eventFilter(watched, event)

    def _on_left_press(self, event):
        """Handle left mouse press: check gizmo hit, then object hit."""
        mx = event.position().x()
        my = event.position().y()

        # 1) Check if clicking on a gizmo axis arrow
        if self._gizmo.visible and self._selected_obj is not None:
            hit_axis = self._pick_gizmo_axis(mx, my)
            if hit_axis is not None:
                self._dragging_axis = hit_axis
                self._drag_last_mouse = (mx, my)
                self._gizmo.highlight_axis(hit_axis)
                return True  # Consume — don't orbit camera

        # 2) Check if clicking on a scene object
        hit_obj = self._pick_object(mx, my)
        if hit_obj is not None:
            self._select_object(hit_obj)
            return False  # Let pyqtgraph handle (camera orbit)

        # 3) Clicked on empty background — deselect
        if self._selected_obj is not None:
            self._deselect()
            return False

        return False  # Let pyqtgraph handle (camera orbit)

    def _on_drag_move(self, event):
        """Handle mouse drag while a gizmo axis is active."""
        if self._dragging_axis is None or self._selected_obj is None:
            return False

        mx = event.position().x()
        my = event.position().y()
        last_x, last_y = self._drag_last_mouse
        dx = mx - last_x
        dy = my - last_y

        if abs(dx) < 0.5 and abs(dy) < 0.5:
            return True

        # Get object position
        obj = self._selected_obj
        obj_pos = np.array([
            float(obj.position[0]),
            float(obj.position[1]),
            float(obj.position[2]),
        ], dtype=np.float32)

        # Get axis world direction
        axis_dir = MoveGizmo.AXIS_DIRS[self._dragging_axis].copy()

        # Project the axis to screen space to determine drag sensitivity
        screen_start = self._world_to_screen(obj_pos)
        screen_end = self._world_to_screen(obj_pos + axis_dir)

        if screen_start is None or screen_end is None:
            self._drag_last_mouse = (mx, my)
            return True

        # Screen-space axis direction
        sdx = screen_end[0] - screen_start[0]
        sdy = screen_end[1] - screen_start[1]
        screen_len = math.sqrt(sdx * sdx + sdy * sdy)

        if screen_len < 1.0:
            self._drag_last_mouse = (mx, my)
            return True

        # Project mouse delta onto the screen-space axis direction
        proj = (dx * sdx + dy * sdy) / screen_len

        # Convert screen pixels to world units
        world_delta = proj / screen_len

        # Apply movement to the object
        obj.position[0] += axis_dir[0] * world_delta
        obj.position[1] += axis_dir[1] * world_delta
        obj.position[2] += axis_dir[2] * world_delta

        # Update gizmo position
        new_pos = np.array([
            float(obj.position[0]),
            float(obj.position[1]),
            float(obj.position[2]),
        ])
        self._gizmo.show_at(new_pos)

        # Emit signal so MainWindow updates the mesh transform and property panel
        self.viewport_object_moved.emit(obj)

        self._drag_last_mouse = (mx, my)
        return True

    # ------------------------------------------------------------------ #
    #  Picking helpers
    # ------------------------------------------------------------------ #

    def _world_to_screen(self, world_pos):
        """Project a 3D world position to 2D screen coordinates."""
        vw = self._gl_view.width()
        vh = self._gl_view.height()

        viewport = (0, 0, vw, vh)
        vm = self._gl_view.viewMatrix()
        pm = self._gl_view.projectionMatrix(region=viewport, viewport=viewport)

        pos4 = QVector4D(
            float(world_pos[0]), float(world_pos[1]),
            float(world_pos[2]), 1.0
        )
        clip = pm.map(vm.map(pos4))

        w = clip.w()
        if abs(w) < 1e-10:
            return None

        # Perspective divide → NDC
        ndcx = clip.x() / w
        ndcy = clip.y() / w

        # NDC → screen pixels
        sx = (ndcx + 1.0) * 0.5 * vw
        sy = (1.0 - ndcy) * 0.5 * vh  # Flip Y (Qt has Y-down)

        return (sx, sy)

    def _pick_gizmo_axis(self, mx, my, threshold=18.0):
        """Check if click is near a gizmo axis line. Returns 'x','y','z' or None."""
        if not self._gizmo.visible:
            return None

        obj = self._selected_obj
        if obj is None:
            return None

        obj_pos = np.array([
            float(obj.position[0]),
            float(obj.position[1]),
            float(obj.position[2]),
        ], dtype=np.float32)

        best_axis = None
        best_dist = threshold

        for axis in ('x', 'y', 'z'):
            d = MoveGizmo.AXIS_DIRS[axis]
            start_3d = obj_pos
            end_3d = obj_pos + d * self._gizmo._shaft_length

            s_start = self._world_to_screen(start_3d)
            s_end = self._world_to_screen(end_3d)
            if s_start is None or s_end is None:
                continue

            dist = self._point_to_segment_dist(mx, my, s_start, s_end)
            if dist < best_dist:
                best_dist = dist
                best_axis = axis

        return best_axis

    def _pick_object(self, mx, my, threshold=35.0):
        """Check if click is near a scene object center. Returns BaseObject or None."""
        from polycad.scene import Document
        doc = Document.instance()
        if not doc:
            return None

        best_obj = None
        best_dist = threshold

        for obj in doc.get_all_objects():
            pos = np.array([
                float(obj.position[0]),
                float(obj.position[1]),
                float(obj.position[2]),
            ])
            screen = self._world_to_screen(pos)
            if screen is None:
                continue
            dist = math.sqrt((mx - screen[0]) ** 2 + (my - screen[1]) ** 2)
            if dist < best_dist:
                best_dist = dist
                best_obj = obj

        return best_obj

    @staticmethod
    def _point_to_segment_dist(px, py, seg_start, seg_end):
        """Distance from point (px,py) to 2D line segment."""
        x1, y1 = seg_start
        x2, y2 = seg_end
        dx, dy = x2 - x1, y2 - y1
        length_sq = dx * dx + dy * dy
        if length_sq < 1e-10:
            return math.sqrt((px - x1) ** 2 + (py - y1) ** 2)
        t = max(0, min(1, ((px - x1) * dx + (py - y1) * dy) / length_sq))
        proj_x = x1 + t * dx
        proj_y = y1 + t * dy
        return math.sqrt((px - proj_x) ** 2 + (py - proj_y) ** 2)

    # ------------------------------------------------------------------ #
    #  Selection management
    # ------------------------------------------------------------------ #

    def _select_object(self, obj):
        """Select an object and show the gizmo at its position."""
        self._selected_obj = obj
        pos = np.array([
            float(obj.position[0]),
            float(obj.position[1]),
            float(obj.position[2]),
        ])
        self._gizmo.show_at(pos)
        self.viewport_object_selected.emit(obj)

    def _deselect(self):
        """Deselect the current object and hide the gizmo."""
        self._selected_obj = None
        self._gizmo.hide()
        self.viewport_object_selected.emit(None)

    def update_gizmo_position(self, obj):
        """Update gizmo position to match object (called after panel edits)."""
        if self._selected_obj is obj and obj is not None:
            pos = np.array([
                float(obj.position[0]),
                float(obj.position[1]),
                float(obj.position[2]),
            ])
            self._gizmo.show_at(pos)

    # ------------------------------------------------------------------ #
    #  Existing API (unchanged)
    # ------------------------------------------------------------------ #

    def add_primitive(self, name, positions, normals, indices, color):
        """Add a primitive mesh to the GL view."""
        vertexes = np.asarray(positions, dtype=np.float32).reshape(-1, 3)
        faces = np.asarray(indices, dtype=np.uint32).reshape(-1, 3)

        print(f"[WIDGET] Adding primitive '{name}': {len(vertexes)} verts, {len(faces)} tris")

        mesh_data = gl.MeshData(vertexes=vertexes, faces=faces)

        num_faces = len(faces)
        face_colors = np.zeros((num_faces, 4), dtype=np.float32)
        face_colors[:, 0] = color[0]
        face_colors[:, 1] = color[1]
        face_colors[:, 2] = color[2]
        face_colors[:, 3] = 1.0
        mesh_data.setFaceColors(face_colors)

        mesh_item = gl.GLMeshItem(
            meshdata=mesh_data,
            smooth=True,
            computeNormals=True,
            shader='shaded',
            drawFaces=True,
            drawEdges=False,
        )

        print(f"[WIDGET] MeshItem created with color=({color[0]:.2f}, {color[1]:.2f}, {color[2]:.2f})")

        mesh_item._name = name
        self._gl_view.addItem(mesh_item)

        self._objects.append({
            'mesh': mesh_item,
            'name': name,
            'position': np.array([0.0, 0.0, 0.0]),
            'size': self._estimate_size(vertexes),
            'factory': None,
        })

        return mesh_item

    def _estimate_size(self, positions):
        if len(positions) == 0:
            return np.array([1.0, 1.0, 1.0])
        return positions.max(axis=0) - positions.min(axis=0)

    def get_gl_view(self):
        return self._gl_view

    def clear_scene(self):
        """Remove all mesh objects and hide gizmo."""
        self._deselect()
        for item in list(self._gl_view.items):
            if isinstance(item, gl.GLMeshItem) and hasattr(item, '_name'):
                self._gl_view.removeItem(item)
        self._objects = []

    def get_object_at_position(self, spacing):
        for attempt in range(16):
            col = attempt % 4
            row = attempt // 4
            x = (col - 1.5) * spacing
            z = (row - 0.5) * spacing
            candidate_pos = np.array([x, 0.0, z])
            has_collision = False
            for obj in self._objects:
                mesh = obj.get('mesh')
                if mesh is None or not hasattr(mesh, '_name'):
                    continue
                other_size = obj.get('size', np.array([1.0, 1.0, 1.0]))
                other_pos = obj['position']
                min_dist = (other_size + np.array([0.5, 0.5, 0.5])) / 2.0
                if (abs(candidate_pos[0] - other_pos[0]) < min_dist[0] and
                    abs(candidate_pos[1] - other_pos[1]) < min_dist[1] and
                    abs(candidate_pos[2] - other_pos[2]) < min_dist[2]):
                    has_collision = True
                    break
            if not has_collision:
                return candidate_pos
        return np.array([0.0, 0.5 + len(self._objects) * 0.3, 0.0])

    def remove_mesh_item(self, mesh_item):
        if mesh_item is not None:
            # If we're removing the selected object's mesh, deselect
            if (self._selected_obj is not None and
                    getattr(self._selected_obj, '_mesh_item', None) is mesh_item):
                self._deselect()
            try:
                self._gl_view.removeItem(mesh_item)
            except Exception:
                pass
        self._objects = [obj for obj in self._objects if obj.get('mesh') is not mesh_item]

    def set_wireframe(self, enabled):
        for item in self._gl_view.items:
            if isinstance(item, gl.GLMeshItem) and hasattr(item, '_name'):
                item.setGLOptions('translucent' if enabled else 'opaque')
                item.opts['drawEdges'] = enabled
                item.opts['edgeColor'] = (1.0, 1.0, 1.0, 0.4)
                item.meshDataChanged()

    def update_mesh_color(self, mesh_item, color_rgb):
        if mesh_item is None:
            return
        md = mesh_item.opts.get('meshdata', None)
        if md is None:
            return
        faces = md.faces()
        if faces is None:
            return
        num_faces = len(faces)
        face_colors = np.zeros((num_faces, 4), dtype=np.float32)
        face_colors[:, 0] = color_rgb[0]
        face_colors[:, 1] = color_rgb[1]
        face_colors[:, 2] = color_rgb[2]
        face_colors[:, 3] = 1.0
        md.setFaceColors(face_colors)
        mesh_item.meshDataChanged()


def paint_fps_overlay(painter, fps: float):
    """Paint FPS counter in bottom-left corner."""
    from PySide6.QtGui import QColor
    painter.setPen(QColor(200, 255, 200))
    painter.drawText(10, 20, f"{fps:.0f} FPS")

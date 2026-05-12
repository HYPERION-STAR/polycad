"""Main application window layout."""

import math
import numpy as np

from PySide6.QtWidgets import (
    QMainWindow, QSplitter, QVBoxLayout, QWidget, QStatusBar,
    QLabel, QMessageBox,
)
from PySide6.QtGui import QAction
from PySide6.QtCore import Qt, QTimer, QElapsedTimer


# ====================================================================== #
#  Undo/Redo command classes
# ====================================================================== #

class AddObjectCommand:
    """Undoable command for adding an object to the scene."""

    def __init__(self, window, obj, mesh_item, factory):
        self._window = window
        self._obj = obj
        self._mesh_item = mesh_item
        self._factory = factory

    def undo(self):
        from polycad.scene import Document
        doc = Document.instance()
        if not doc:
            return
        # Remove from GL view
        self._window.gl_widget.remove_mesh_item(self._mesh_item)
        # Remove from layer order
        L = doc._find_layer_of(self._obj.id)
        if L is not None and self._obj.id in L._object_ids:
            L._object_ids.remove(self._obj.id)
        # Remove from document
        if self._obj in doc._objects:
            doc._objects.remove(self._obj)
        doc._selected_ids.discard(self._obj.id)
        self._window.object_tree.update_tree()
        self._window.prop_panel.update_for_object(None)
        self._window._refresh_render_order()
        self._window.statusbar.showMessage(f"Undo: removed {self._obj.name}.")

    def redo(self):
        from polycad.scene import Document
        doc = Document.instance()
        if not doc:
            return
        # Re-add to GL view
        self._window.gl_widget._gl_view.addItem(self._mesh_item)
        self._window.gl_widget._objects.append({
            'mesh': self._mesh_item,
            'name': self._obj.name,
            'position': self._obj.position.copy(),
            'size': np.array([1.0, 1.0, 1.0]),
            'factory': self._factory,
        })
        # Re-add to document
        doc._objects.append(self._obj)
        doc._selected_ids = {self._obj.id}
        # Restore to its original layer (frontmost slot)
        target = doc.get_layer(self._obj.layer_id) if self._obj.layer_id is not None else None
        if target is None:
            target = doc.get_active_layer()
            self._obj.layer_id = target.id
        if self._obj.id not in target._object_ids:
            target._object_ids.append(self._obj.id)
        self._window._apply_transform_to_mesh(self._obj)
        self._window.object_tree.update_tree()
        self._window.prop_panel.update_for_object(self._obj)
        self._window._refresh_render_order()
        self._window.statusbar.showMessage(f"Redo: re-added {self._obj.name}.")


class DeleteObjectsCommand:
    """Undoable command for deleting objects from the scene."""

    def __init__(self, window, deleted_objects):
        """deleted_objects: list of (obj, mesh_item, layer_id, layer_index) tuples."""
        self._window = window
        self._deleted = deleted_objects

    def undo(self):
        from polycad.scene import Document
        doc = Document.instance()
        if not doc:
            return
        for obj, mesh_item, layer_id, layer_index in self._deleted:
            # Re-add to GL view
            if mesh_item is not None:
                self._window.gl_widget._gl_view.addItem(mesh_item)
                self._window.gl_widget._objects.append({
                    'mesh': mesh_item,
                    'name': obj.name,
                    'position': obj.position.copy(),
                    'size': np.array([1.0, 1.0, 1.0]),
                })
                obj._mesh_item = mesh_item
            doc._objects.append(obj)
            # Restore to original layer at original index (clamped)
            target = doc.get_layer(layer_id) if layer_id is not None else None
            if target is None:
                target = doc.get_active_layer()
            obj.layer_id = target.id
            insert_at = max(0, min(layer_index, len(target._object_ids)))
            target._object_ids.insert(insert_at, obj.id)
            self._window._apply_transform_to_mesh(obj)
        self._window.object_tree.update_tree()
        self._window._refresh_render_order()
        count = len(self._deleted)
        self._window.statusbar.showMessage(f"Undo: restored {count} object(s).")

    def redo(self):
        from polycad.scene import Document
        doc = Document.instance()
        if not doc:
            return
        for obj, mesh_item, _layer_id, _layer_index in self._deleted:
            if mesh_item is not None:
                self._window.gl_widget.remove_mesh_item(mesh_item)
            L = doc._find_layer_of(obj.id)
            if L is not None and obj.id in L._object_ids:
                L._object_ids.remove(obj.id)
            if obj in doc._objects:
                doc._objects.remove(obj)
            doc._selected_ids.discard(obj.id)
        self._window.object_tree.update_tree()
        self._window.prop_panel.update_for_object(None)
        self._window._refresh_render_order()
        count = len(self._deleted)
        self._window.statusbar.showMessage(f"Redo: deleted {count} object(s).")


class ModifyObjectsCommand:
    """Undoable command for changing N objects' properties at once.

    Each entry in `edits` is (obj_id, old_data, new_data). Single-object
    edits use the same path; multi-object edits batch into one undo unit
    so Ctrl+Z reverts the whole multi-select rotation/translation/etc.
    """

    def __init__(self, window, edits):
        self._window = window
        self._edits = [(o.id, old, new) for (o, old, new) in edits]

    def undo(self):
        self._apply([(oid, old) for (oid, old, _new) in self._edits],
                    f"Undo: reverted {len(self._edits)} change(s).")

    def redo(self):
        self._apply([(oid, new) for (oid, _old, new) in self._edits],
                    f"Redo: re-applied {len(self._edits)} change(s).")

    def _apply(self, pairs, msg):
        from polycad.scene import Document
        doc = Document.instance()
        if not doc:
            return
        touched_primary = None
        for obj_id, data in pairs:
            obj = doc.get_object_by_id(obj_id)
            if obj is None:
                continue
            obj.from_data(data)
            self._window._apply_transform_to_mesh(obj)
            self._window._update_mesh_color_for(obj)
            if obj.id in doc.selected_ids:
                touched_primary = obj
        if touched_primary is not None:
            self._window.gl_widget.update_gizmo_position(touched_primary)
            sel = [doc.get_object_by_id(i) for i in doc.selected_ids]
            sel = [o for o in sel if o is not None]
            self._window.prop_panel.update_for_objects(sel)
        self._window.statusbar.showMessage(msg)

# ====================================================================== #
#  Main Window
# ====================================================================== #

class MainWindow(QMainWindow):
    """Main application window with OpenGL viewport and UI panels."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("PolyCAD — 3D CAD Application")
        self.resize(1400, 800)

        self._wireframe_on = False
        self._object_counter = {}  # Track per-type counts for naming: {"Box": 3, ...}

        # Initialize document singleton
        from polycad.scene import Document
        Document.create_instance()

        # Build UI
        self._build_menubar()
        self._setup_toolbar()
        self._setup_panels()
        self._setup_statusbar()

        # FPS timer — counts how many GL widget repaints happen per second
        self._fps_timer = QTimer(self)
        self._fps_elapsed = QElapsedTimer()
        self._fps_elapsed.start()
        self._frame_count = 0
        self._fps = 0.0
        self._fps_timer.setInterval(1000)
        self._fps_timer.timeout.connect(self._update_fps_display)
        self._fps_timer.start()

        # Repaint counter — hook into pyqtgraph's paint cycle
        self._hook_fps_counter()

    # ------------------------------------------------------------------ #
    #  Menu bar
    # ------------------------------------------------------------------ #

    def _build_menubar(self):
        """Create menu bar with File and Edit menus."""
        menubar = self.menuBar()

        # File menu
        file_menu = menubar.addMenu("&File")
        new_action = QAction("New Scene", self)
        new_action.setShortcut("Ctrl+N")
        new_action.triggered.connect(self._new_scene)
        file_menu.addAction(new_action)

        file_menu.addSeparator()

        import_action = QAction("Import OBJ...", self)
        import_action.setShortcut("Ctrl+I")
        import_action.triggered.connect(self._import_obj)
        file_menu.addAction(import_action)

        export_action = QAction("Export OBJ...", self)
        export_action.setShortcut("Ctrl+E")
        export_action.triggered.connect(self._export_obj)
        file_menu.addAction(export_action)

        file_menu.addSeparator()

        quit_action = QAction("Quit", self)
        quit_action.setShortcut("Alt+F4")
        quit_action.triggered.connect(self.close)
        file_menu.addAction(quit_action)

        # Edit menu
        edit_menu = menubar.addMenu("&Edit")
        undo_action = QAction("Undo", self)
        undo_action.setShortcut("Ctrl+Z")
        undo_action.triggered.connect(self._undo)
        edit_menu.addAction(undo_action)

        redo_action = QAction("Redo", self)
        redo_action.setShortcut("Ctrl+Y")
        redo_action.triggered.connect(self._redo)
        edit_menu.addAction(redo_action)

        edit_menu.addSeparator()

        select_all_action = QAction("Select All", self)
        select_all_action.setShortcut("Ctrl+A")
        select_all_action.triggered.connect(self._select_all)
        edit_menu.addAction(select_all_action)

        delete_action = QAction("Delete Selected", self)
        delete_action.setShortcut("Delete")
        delete_action.triggered.connect(self._delete_selected)
        edit_menu.addAction(delete_action)

        # View menu
        view_menu = menubar.addMenu("&View")

        wireframe_action = QAction("Toggle Wireframe", self)
        wireframe_action.setShortcut("F")
        wireframe_action.triggered.connect(self._toggle_wireframe)
        view_menu.addAction(wireframe_action)

        reset_cam_action = QAction("Reset Camera", self)
        reset_cam_action.setShortcut("Numpad0")
        reset_cam_action.triggered.connect(self._reset_camera)
        view_menu.addAction(reset_cam_action)

    # ------------------------------------------------------------------ #
    #  Toolbar
    # ------------------------------------------------------------------ #

    def _setup_toolbar(self):
        """Create and attach the toolbar widget (custom QWidget)."""
        from polycad.ui import Toolbar
        from polycad.scene import PRIMITIVE_FACTORIES
        import functools

        self.toolbar = Toolbar()

        # Primitive creation buttons
        def make_callback(prim_name: str):
            factory = PRIMITIVE_FACTORIES[prim_name]
            return functools.partial(self._add_primitive, factory, prim_name.title())

        for prim in ("box", "cylinder", "sphere", "cone"):
            btn = getattr(self.toolbar, f"_btn_{prim}")
            btn.clicked.connect(make_callback(prim))

        # Wireframe toggle
        self.toolbar._btn_wireframe.clicked.connect(self._toggle_wireframe)

        # Delete button
        self.toolbar._btn_delete.clicked.connect(self._delete_selected)

    # ------------------------------------------------------------------ #
    #  Panels
    # ------------------------------------------------------------------ #

    def _setup_panels(self):
        """Create and arrange the scene panels."""
        from polycad.viewport import OpenGLWidget
        from polycad.ui import ObjectTreePanel, PropertyPanel

        # Central widget — minimal margins so viewport fills space
        central = QWidget()
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Top row: toolbar
        main_layout.addWidget(self.toolbar)

        # Bottom row: object tree | opengl viewport | properties panel
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(2)
        splitter.setChildrenCollapsible(False)

        self.object_tree = ObjectTreePanel()
        splitter.addWidget(self.object_tree)

        self.gl_widget = OpenGLWidget()
        splitter.addWidget(self.gl_widget)

        self.prop_panel = PropertyPanel()
        splitter.addWidget(self.prop_panel)

        # Give the viewport (index 1) much more space
        splitter.setSizes([180, 1100, 240])
        splitter.setStretchFactor(0, 0)  # Tree: don't grow
        splitter.setStretchFactor(1, 1)  # Viewport: takes all extra space
        splitter.setStretchFactor(2, 0)  # Props: don't grow

        main_layout.addWidget(splitter)

        # Status bar
        self.fps_label = QLabel("FPS: --")
        self.obj_count_label = QLabel("Objects: 0")
        self.statusbar = QStatusBar()
        self.statusbar.addPermanentWidget(self.obj_count_label)
        self.statusbar.addPermanentWidget(self.fps_label)
        self.setStatusBar(self.statusbar)

        # Connect signals
        self.object_tree.selection_changed_multi.connect(self._on_tree_selection_changed)
        self.prop_panel.transform_changed.connect(self._on_transform_changed)
        self.prop_panel.color_changed.connect(self._on_color_changed)

        # Viewport click-to-select and gizmo drag signals
        self.gl_widget.viewport_object_selected.connect(self._on_viewport_select)
        self.gl_widget.viewport_object_moved.connect(self._on_viewport_move)
        self.gl_widget.viewport_drag_finished.connect(self._on_property_edit_finished)
        
        self.prop_panel.property_edit_finished.connect(self._on_property_edit_finished)

        # Tree-driven rename
        self.object_tree.object_renamed.connect(self._on_object_renamed)

        # Layer / z-order signals from ObjectTreePanel
        self.object_tree.object_reorder_requested.connect(self._on_object_reorder)
        self.object_tree.move_object_to_layer_requested.connect(self._on_move_object_to_layer)
        self.object_tree.new_layer_requested.connect(self._on_new_layer)
        self.object_tree.delete_layer_requested.connect(self._on_delete_layer)
        self.object_tree.rename_layer_requested.connect(self._on_rename_layer)
        self.object_tree.layer_visibility_toggled.connect(self._on_layer_visibility_toggled)
        self.object_tree.layer_lock_toggled.connect(self._on_layer_lock_toggled)
        self.object_tree.layer_move_requested.connect(self._on_layer_move)
        self.object_tree.active_layer_changed.connect(self._on_active_layer_changed)

        self.setCentralWidget(central)

    def _setup_statusbar(self):
        """Initialize status bar."""
        self.statusbar.showMessage("PolyCAD — Ready. Add primitives from toolbar.")

    # ------------------------------------------------------------------ #
    #  FPS counter
    # ------------------------------------------------------------------ #

    def _hook_fps_counter(self):
        """Hook into pyqtgraph's GLViewWidget repaint to count frames."""
        original_paint = self.gl_widget._gl_view.paintGL

        def counting_paint():
            self._frame_count += 1
            original_paint()

        self.gl_widget._gl_view.paintGL = counting_paint

    def _update_fps_display(self):
        """Update FPS counter — called every 1 second."""
        elapsed_ms = self._fps_elapsed.elapsed()
        if elapsed_ms > 0:
            self._fps = self._frame_count * 1000.0 / elapsed_ms
        self.fps_label.setText(f"FPS: {self._fps:.0f}")
        self._frame_count = 0
        self._fps_elapsed.restart()

    # ------------------------------------------------------------------ #
    #  Tool change
    # ------------------------------------------------------------------ #

    def _on_tool_changed(self, tool_name: str):
        """Handle transform tool selection from toolbar."""
        self._active_tool = tool_name
        display = tool_name.title()
        self.tool_label.setText(f"Tool: {display}")
        self.statusbar.showMessage(f"Active tool: {display}")

    # ------------------------------------------------------------------ #
    #  Wireframe toggle
    # ------------------------------------------------------------------ #

    def _toggle_wireframe(self):
        """Toggle wireframe rendering on all objects."""
        self._wireframe_on = not self._wireframe_on
        self.gl_widget.set_wireframe(self._wireframe_on)
        # Keep toolbar button in sync
        self.toolbar._btn_wireframe.setChecked(self._wireframe_on)
        state = "ON" if self._wireframe_on else "OFF"
        self.statusbar.showMessage(f"Wireframe: {state}")

    # ------------------------------------------------------------------ #
    #  Camera reset
    # ------------------------------------------------------------------ #

    def _reset_camera(self):
        """Reset camera to default position."""
        self.gl_widget._gl_view.setCameraPosition(
            distance=5.0, elevation=30.0, azimuth=-45.0
        )
        self.statusbar.showMessage("Camera reset.")

    # ------------------------------------------------------------------ #
    #  Add primitive (with undo support)
    # ------------------------------------------------------------------ #

    def _add_primitive(self, factory, name: str):
        """Add a primitive object to the scene with undo support."""
        from polycad.scene import BaseObject
        from polycad.scene import Document

        positions, normals, indices = factory()

        doc = Document.instance()
        if not doc:
            return

        obj = BaseObject(name=name)

        # Auto-number: Box.1, Box.2, Cylinder.1, etc.
        count = self._object_counter.get(name, 0) + 1
        self._object_counter[name] = count
        obj._display_name = f"{name}.{count}"

        # Vibrant colors for better 3D visibility with lighting
        colors = {
            "Box": (0.39, 0.69, 1.0),
            "Cylinder": (0.33, 0.94, 0.63),
            "Sphere": (1.0, 0.76, 0.39),
            "Cone": (1.0, 0.51, 0.71),
        }
        color = colors.get(name, (0.78, 0.78, 0.86))
        obj.set_color(*color)

        try:
            mesh_item = self.gl_widget.add_primitive(
                name=name,
                positions=positions,
                normals=normals,
                indices=indices,
                color=color,
            )
        except Exception as e:
            print(f"[ERROR] Failed to add primitive mesh: {e}")
            import traceback
            traceback.print_exc()
            return

        # Auto-position: find non-overlapping slot
        spacing = 2.5
        position = self.gl_widget.get_object_at_position(spacing)

        obj.position[0] = position[0]
        obj.position[1] = position[1]
        obj.position[2] = position[2]

        doc.add_object(obj)
        obj._mesh_item = mesh_item
        obj._factory = factory

        # Update tracked object position in GL widget
        for tracked in self.gl_widget._objects:
            if tracked['mesh'] is mesh_item:
                tracked['position'] = position
                break

        # Apply the initial transform
        self._apply_transform_to_mesh(obj)

        # Push undo command
        cmd = AddObjectCommand(self, obj, mesh_item, factory)
        doc.push_command(cmd)

        self._update_object_count()
        self.object_tree.update_tree()
        self.prop_panel.update_for_object(obj)
        self._refresh_render_order()
        self.statusbar.showMessage(
            f"Added {name} to scene ({doc.get_active_layer().name})."
        )

    # ------------------------------------------------------------------ #
    #  Delete selected (with undo support)
    # ------------------------------------------------------------------ #

    def _delete_selected(self):
        """Delete selected objects with undo support."""
        from polycad.scene import Document
        doc = Document.instance()
        if not doc:
            return

        selected = list(doc.selected_ids)
        if not selected:
            self.statusbar.showMessage("No objects selected to delete.")
            return

        # Collect objects and their mesh items for undo
        deleted_records = []
        for obj_id in selected:
            obj = doc.get_object_by_id(obj_id)
            if obj:
                mesh_item = getattr(obj, '_mesh_item', None)
                # Snapshot the layer location for proper undo restoration
                L = doc._find_layer_of(obj.id)
                layer_id = L.id if L else None
                layer_index = L._object_ids.index(obj.id) if L and obj.id in L._object_ids else 0
                deleted_records.append((obj, mesh_item, layer_id, layer_index))
                # Remove from GL view
                if mesh_item is not None:
                    self.gl_widget.remove_mesh_item(mesh_item)
                # Remove from layer
                if L is not None and obj.id in L._object_ids:
                    L._object_ids.remove(obj.id)
                # Remove from document
                if obj in doc._objects:
                    doc._objects.remove(obj)

        doc._selected_ids.clear()

        # Push undo command
        if deleted_records:
            cmd = DeleteObjectsCommand(self, deleted_records)
            doc.push_command(cmd)

        count = len(deleted_records)
        self.statusbar.showMessage(f"Deleted {count} object(s).")
        self._update_object_count()
        self.object_tree.update_tree()
        self.prop_panel.update_for_object(None)
        self._refresh_render_order()

    # ------------------------------------------------------------------ #
    #  Undo / Redo
    # ------------------------------------------------------------------ #

    def _undo(self):
        """Execute undo command."""
        from polycad.scene import Document
        doc = Document.instance()
        if doc and doc.undo():
            self._update_object_count()
            self.statusbar.showMessage("Undo executed.")
        else:
            self.statusbar.showMessage("Nothing to undo.")

    def _redo(self):
        """Execute redo command."""
        from polycad.scene import Document
        doc = Document.instance()
        if doc and doc.redo():
            self._update_object_count()
            self.statusbar.showMessage("Redo executed.")
        else:
            self.statusbar.showMessage("Nothing to redo.")

    # ------------------------------------------------------------------ #
    #  New scene
    # ------------------------------------------------------------------ #

    def _new_scene(self):
        """Create a new empty scene."""
        reply = QMessageBox.question(
            self, "New Scene",
            "Clear the current scene? Unsaved changes will be lost.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.gl_widget.clear_scene()
            self._object_counter = {}  # Reset naming counter

            from polycad.scene import Document
            doc = Document.instance()
            for obj in list(doc.get_all_objects()):
                if hasattr(obj, '_mesh_item'):
                    delattr(obj, '_mesh_item')
            doc.destroy_instance()
            Document.create_instance()
            self._update_object_count()
            self.object_tree.update_tree()
            self.prop_panel.update_for_object(None)
            self.statusbar.showMessage("New scene created.")

    # ------------------------------------------------------------------ #
    #  Export OBJ
    # ------------------------------------------------------------------ #

    def _export_obj(self):
        """Export scene to OBJ file."""
        from PySide6.QtWidgets import QFileDialog
        from polycad.scene import Document

        doc = Document.instance()
        if not doc:
            return

        objects = doc.get_all_objects()
        if not objects:
            self.statusbar.showMessage("Nothing to export — scene is empty.")
            return

        path, _ = QFileDialog.getSaveFileName(
            self, "Export OBJ", "", "OBJ Files (*.obj);;All Files (*)"
        )
        if not path:
            return

        vertex_offset = 0
        with open(path, "w") as f:
            f.write("# PolyCAD OBJ Export\n\n")
            for obj in objects:
                factory = getattr(obj, '_factory', None)
                if not factory:
                    continue

                positions, normals, indices = factory()
                num_verts = len(positions)

                f.write(f"o {obj.name}\n")

                # Embed original transforms and color as PolyCAD specific metadata
                f.write(f"# PolyCADData: color {obj.color[0]:.6f} {obj.color[1]:.6f} {obj.color[2]:.6f}\n")
                f.write(f"# PolyCADData: pos {obj.position[0]:.6f} {obj.position[1]:.6f} {obj.position[2]:.6f}\n")
                f.write(f"# PolyCADData: rot {obj.rotation_euler[0]:.6f} {obj.rotation_euler[1]:.6f} {obj.rotation_euler[2]:.6f}\n")
                f.write(f"# PolyCADData: scale {obj.scale[0]:.6f} {obj.scale[1]:.6f} {obj.scale[2]:.6f}\n")

                # Write raw vertices (NOT transformed, because we save the transform above)
                for i in range(num_verts):
                    px, py, pz = positions[i]
                    f.write(f"v {px:.6f} {py:.6f} {pz:.6f}\n")

                for i in range(num_verts):
                    nx, ny, nz = normals[i]
                    f.write(f"vn {nx:.6f} {ny:.6f} {nz:.6f}\n")

                for face in indices:
                    idx0 = face[0] + 1 + vertex_offset
                    idx1 = face[1] + 1 + vertex_offset
                    idx2 = face[2] + 1 + vertex_offset
                    f.write(f"f {idx0}//{idx0} {idx1}//{idx1} {idx2}//{idx2}\n")

                vertex_offset += num_verts
                f.write("\n")

        self.statusbar.showMessage(f"Exported {len(objects)} object(s) to {path}")

    # ------------------------------------------------------------------ #
    #  Import OBJ
    # ------------------------------------------------------------------ #

    def _import_obj(self):
        """Import an OBJ file into the scene."""
        from PySide6.QtWidgets import QFileDialog
        from polycad.scene import Document
        from polycad.scene import BaseObject
        import os

        path, _ = QFileDialog.getOpenFileName(
            self, "Import OBJ", "",
            "OBJ Files (*.obj);;All Files (*)"
        )
        if not path:
            return

        doc = Document.instance()
        if not doc:
            return

        try:
            objects_imported = self._parse_obj_file(path)
        except Exception as e:
            self.statusbar.showMessage(f"Import failed: {e}")
            return

        if not objects_imported:
            self.statusbar.showMessage("No geometry found in OBJ file.")
            return

        for obj_name, positions, normals, indices, metadata in objects_imported:
            # Use filename as name if no object name in file
            if not obj_name:
                obj_name = os.path.splitext(os.path.basename(path))[0]

            obj = BaseObject(name=obj_name)
            
            # Restore metadata if it came from PolyCAD, otherwise use sensible defaults
            color = metadata.get('color', (0.7, 0.7, 0.85))
            obj.set_color(*color)
            
            pos = metadata.get('pos', (0.0, 0.0, 0.0))
            obj.position = np.array(pos, dtype=np.float32)
            
            rot = metadata.get('rot', (0.0, 0.0, 0.0))
            obj.rotation_euler = np.array(rot, dtype=np.float32)
            
            scale = metadata.get('scale', (1.0, 1.0, 1.0))
            obj.scale = np.array(scale, dtype=np.float32)

            # If it's a generic third-party OBJ without metadata, center the vertices 
            # so the pivot point isn't millions of miles away from the mesh
            if 'pos' not in metadata and len(positions) > 0:
                min_bounds = np.min(positions, axis=0)
                max_bounds = np.max(positions, axis=0)
                centroid = (min_bounds + max_bounds) / 2.0
                positions = positions - centroid
                obj.position = np.array(centroid, dtype=np.float32)

            try:
                mesh_item = self.gl_widget.add_primitive(
                    name=obj_name,
                    positions=positions,
                    normals=normals,
                    indices=indices,
                    color=color,
                )
            except Exception as e:
                print(f"[ERROR] Failed to add imported mesh '{obj_name}': {e}")
                continue

            doc.add_object(obj)
            obj._mesh_item = mesh_item
            # Store a lambda factory so export can re-generate the data
            _p, _n, _i = positions.copy(), normals.copy(), indices.copy()
            obj._factory = lambda _p=_p, _n=_n, _i=_i: (_p, _n, _i)

            self._apply_transform_to_mesh(obj)

        count = len(objects_imported)
        self._update_object_count()
        self.object_tree.update_tree()
        if objects_imported:
            # Select the last imported object
            last_obj = doc.get_all_objects()[-1]
            self.prop_panel.update_for_object(last_obj)
        self._refresh_render_order()
        self.statusbar.showMessage(
            f"Imported {count} object(s) from {os.path.basename(path)}"
        )

    def _parse_obj_file(self, path: str):
        """Parse a Wavefront OBJ file into mesh data.

        Supports:
          - v (vertex positions)
          - vn (vertex normals)
          - f (faces with v, v//vn, v/vt, v/vt/vn formats)
          - o (object groups)

        Returns:
            List of (name, positions, normals, indices) tuples.
            positions: np.ndarray (N, 3)
            normals:   np.ndarray (N, 3)
            indices:   np.ndarray (M,) uint32
        """
        all_verts = []   # Global vertex list (1-indexed in OBJ)
        all_normals = [] # Global normal list

        # Current object being parsed
        current_name = ""
        current_faces = []  # list of [(vi, ni), ...] per face
        current_metadata = {}

        results = []

        def _flush_object():
            """Convert accumulated faces into arrays and append to results."""
            nonlocal current_name, current_faces, current_metadata
            if not current_faces:
                return

            # Build deduplicated vertex list from (vi, ni) pairs
            unique_verts = {}  # (vi, ni) -> new_index
            out_positions = []
            out_normals = []
            out_indices = []

            for face_verts in current_faces:
                # Triangulate: fan from first vertex for polygons > 3 verts
                for tri in range(1, len(face_verts) - 1):
                    for local_idx in (0, tri, tri + 1):
                        vi, ni = face_verts[local_idx]
                        key = (vi, ni)
                        if key not in unique_verts:
                            idx = len(out_positions)
                            unique_verts[key] = idx
                            # OBJ is 1-indexed
                            if 0 <= vi < len(all_verts):
                                out_positions.append(all_verts[vi])
                            else:
                                out_positions.append([0.0, 0.0, 0.0])
                            if 0 <= ni < len(all_normals):
                                out_normals.append(all_normals[ni])
                            else:
                                out_normals.append([0.0, 1.0, 0.0])
                        out_indices.append(unique_verts[key])

            if out_positions:
                results.append((
                    current_name,
                    np.array(out_positions, dtype=np.float32),
                    np.array(out_normals, dtype=np.float32),
                    np.array(out_indices, dtype=np.uint32).reshape(-1, 3),
                    current_metadata
                ))

            current_faces = []
            current_metadata = {}

        with open(path, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                    
                if line.startswith("#"):
                    if line.startswith("# PolyCADData:"):
                        parts = line.split()
                        if len(parts) >= 6:
                            key = parts[2]
                            vals = (float(parts[3]), float(parts[4]), float(parts[5]))
                            current_metadata[key] = vals
                    continue

                parts = line.split()
                keyword = parts[0]

                if keyword == "v" and len(parts) >= 4:
                    all_verts.append([
                        float(parts[1]), float(parts[2]), float(parts[3])
                    ])

                elif keyword == "vn" and len(parts) >= 4:
                    all_normals.append([
                        float(parts[1]), float(parts[2]), float(parts[3])
                    ])

                elif keyword == "o" or keyword == "g":
                    _flush_object()
                    current_name = parts[1] if len(parts) > 1 else ""

                elif keyword == "f":
                    face = []
                    for vert_str in parts[1:]:
                        # Parse face vertex: v, v/vt, v//vn, v/vt/vn
                        components = vert_str.split("/")
                        vi = int(components[0]) - 1  # Convert to 0-indexed
                        ni = -1
                        if len(components) >= 3 and components[2]:
                            ni = int(components[2]) - 1
                        elif len(components) == 2 and components[1]:
                            # v/vt format — no normal
                            ni = -1
                        face.append((vi, ni))
                    current_faces.append(face)

        # Flush the last object
        _flush_object()

        # If no 'o'/'g' lines, everything goes into one object
        if not results and current_faces:
            _flush_object()

        return results

    # ------------------------------------------------------------------ #
    #  Selection change
    # ------------------------------------------------------------------ #

    def _on_tree_selection_changed(self, obj_ids: list):
        """Handle multi-selection from the object tree — drives Document
        state, PropertyPanel and gizmo all at once."""
        from polycad.scene import Document
        doc = Document.instance()
        if not doc:
            return

        if not obj_ids:
            doc.selected_ids = set()
            self.prop_panel.update_for_objects([])
            self.gl_widget._deselect()
            return

        doc.selected_ids = set(obj_ids)
        sel = [doc.get_object_by_id(i) for i in obj_ids]
        sel = [o for o in sel if o is not None]
        if not sel:
            return
        primary = sel[-1]
        self.prop_panel.update_for_objects(sel)
        # Gizmo follows the primary; other selected objects move with it
        # via the delta-apply logic in viewport drag.
        self.gl_widget._selected_obj = primary
        self.gl_widget._gizmo.show_at(primary.position.copy())

    # ------------------------------------------------------------------ #
    #  Viewport click-to-select and gizmo drag
    # ------------------------------------------------------------------ #

    def _on_viewport_select(self, obj):
        """Called when user clicks an object (or background) in the viewport."""
        from polycad.scene import Document
        doc = Document.instance()
        if not doc:
            return

        if obj is not None:
            doc.selected_ids = {obj.id}
            self.prop_panel.update_for_object(obj)
            self.object_tree.update_tree()
            self.statusbar.showMessage(
                f"Selected: {getattr(obj, '_display_name', obj.name)}"
            )
        else:
            doc.deselect_all()
            self.prop_panel.update_for_object(None)
            self.object_tree.update_tree()
            self.statusbar.showMessage("Selection cleared.")

    def _on_viewport_move(self, obj):
        """Called in real-time while the user drags a gizmo axis.
        Every selected object's mesh transform is refreshed so multi-select
        drags move the whole group together."""
        from polycad.scene import Document
        doc = Document.instance()
        if doc and obj is not None and obj.id in doc.selected_ids and len(doc.selected_ids) > 1:
            for oid in doc.selected_ids:
                o = doc.get_object_by_id(oid)
                if o is not None:
                    self._apply_transform_to_mesh(o)
            sel = [doc.get_object_by_id(i) for i in doc.selected_ids]
            sel = [o for o in sel if o is not None]
            self.prop_panel.update_for_objects(sel)
        else:
            self._apply_transform_to_mesh(obj)
            self.prop_panel.update_for_object(obj)

    # ------------------------------------------------------------------ #
    #  Transform sync — property panel → GL viewport
    # ------------------------------------------------------------------ #

    def _on_transform_changed(self, obj):
        """Spinbox edit fired from PropertyPanel. Apply the resulting
        transform to ALL selected objects' meshes so multi-select rotation
        / translation / scale stays visible in the viewport."""
        from polycad.scene import Document
        doc = Document.instance()
        if doc and obj is not None and obj.id in doc.selected_ids and len(doc.selected_ids) > 1:
            for oid in doc.selected_ids:
                o = doc.get_object_by_id(oid)
                if o is not None:
                    self._apply_transform_to_mesh(o)
        else:
            self._apply_transform_to_mesh(obj)
        # Gizmo trails the primary
        self.gl_widget.update_gizmo_position(obj)

    def _on_color_changed(self, obj):
        """Called when the user picks a new color in the panel (per-object)."""
        self._update_mesh_color_for(obj)

    def _update_mesh_color_for(self, obj):
        """Helper: push the object's current colour into its GL mesh item."""
        if obj is None:
            return
        mesh_item = getattr(obj, '_mesh_item', None)
        if mesh_item is not None:
            self.gl_widget.update_mesh_color(
                mesh_item,
                (float(obj.color[0]), float(obj.color[1]), float(obj.color[2]))
            )

    def _on_property_edit_finished(self, edits: list):
        """Called when a spinbox edit session or viewport drag concludes.
        `edits` is a list of (obj, old_data, new_data) tuples — batches
        into one undo entry covering the whole multi-edit."""
        if not edits:
            return
        from polycad.scene import Document
        doc = Document.instance()
        if doc:
            cmd = ModifyObjectsCommand(self, edits)
            doc.push_command(cmd)

    def _apply_transform_to_mesh(self, obj):
        """Build a pyqtgraph Transform3D from the object and apply it."""
        mesh_item = getattr(obj, '_mesh_item', None)
        if mesh_item is None:
            return

        import pyqtgraph as pg

        tr = pg.Transform3D()

        # Order: Translate → Rotate (XYZ) → Scale
        tr.translate(
            float(obj.position[0]),
            float(obj.position[1]),
            float(obj.position[2]),
        )
        rx = math.degrees(float(obj.rotation_euler[0]))
        ry = math.degrees(float(obj.rotation_euler[1]))
        rz = math.degrees(float(obj.rotation_euler[2]))
        tr.rotate(rx, 1, 0, 0)
        tr.rotate(ry, 0, 1, 0)
        tr.rotate(rz, 0, 0, 1)

        tr.scale(
            float(obj.scale[0]),
            float(obj.scale[1]),
            float(obj.scale[2]),
        )

        mesh_item.setTransform(tr)

        # Keep the tracked position in sync for collision detection
        for tracked in self.gl_widget._objects:
            if tracked['mesh'] is mesh_item:
                tracked['position'] = obj.position.copy()
                break

    # ------------------------------------------------------------------ #
    #  Helpers
    # ------------------------------------------------------------------ #

    def _update_object_count(self):
        """Update the object count label in the status bar."""
        from polycad.scene import Document
        doc = Document.instance()
        count = len(doc.get_all_objects()) if doc else 0
        self.obj_count_label.setText(f"Objects: {count}")

    # ------------------------------------------------------------------ #
    #  Select-all
    # ------------------------------------------------------------------ #

    def _select_all(self):
        """Ctrl+A — select every object that lives in a visible, unlocked layer.
        Drives the tree's multi-selection so the PropertyPanel switches into
        multi-edit mode and subsequent rotates / moves / scales / colour
        picks / deletes fan out across the whole selection."""
        from polycad.scene import Document
        from PySide6.QtCore import Qt as _Qt
        doc = Document.instance()
        if not doc:
            return

        ids: list[int] = []
        for obj in doc.get_all_objects():
            visible, locked = doc.get_object_render_state(obj.id)
            if visible and not locked:
                ids.append(obj.id)

        if not ids:
            self.statusbar.showMessage("Nothing to select.")
            return

        doc.selected_ids = set(ids)

        # Reflect the selection in the tree without firing per-row signals
        tree = self.object_tree.tree
        tree.blockSignals(True)
        try:
            it = tree.topLevelItemCount()
            for i in range(it):
                layer_item = tree.topLevelItem(i)
                for j in range(layer_item.childCount()):
                    child = layer_item.child(j)
                    cid = child.data(0, _Qt.ItemDataRole.UserRole)
                    if cid is not None and int(cid) in doc.selected_ids:
                        child.setSelected(True)
                    else:
                        child.setSelected(False)
        finally:
            tree.blockSignals(False)

        sel = [doc.get_object_by_id(i) for i in ids]
        sel = [o for o in sel if o is not None]
        self.prop_panel.update_for_objects(sel)
        primary = sel[-1]
        self.gl_widget._selected_obj = primary
        self.gl_widget._gizmo.show_at(primary.position.copy())
        self.statusbar.showMessage(f"Selected {len(sel)} object(s).")

    # ------------------------------------------------------------------ #
    #  Layer / z-order plumbing
    # ------------------------------------------------------------------ #

    def _refresh_render_order(self):
        """Reorder GL view items and update mesh visibility based on layers."""
        from polycad.scene import Document
        doc = Document.instance()
        if not doc:
            return
        ordered = []
        for oid in doc.get_render_order():
            obj = doc.get_object_by_id(oid)
            if obj is None:
                continue
            mesh = getattr(obj, '_mesh_item', None)
            if mesh is not None:
                ordered.append(mesh)
        if ordered:
            self.gl_widget.set_render_order(ordered)
        # Apply per-mesh visibility based on owning layer's `visible` flag
        for obj in doc.get_all_objects():
            mesh = getattr(obj, '_mesh_item', None)
            if mesh is None:
                continue
            visible, _ = doc.get_object_render_state(obj.id)
            self.gl_widget.set_mesh_visibility(mesh, visible)

    def _on_object_reorder(self, action: str, obj_id: int):
        """Bring/Send object within its layer."""
        from polycad.scene import Document
        doc = Document.instance()
        if not doc:
            return
        changed = {
            "front":    doc.bring_to_front,
            "forward":  doc.bring_forward,
            "backward": doc.send_backward,
            "back":     doc.send_to_back,
        }.get(action, lambda _i: False)(obj_id)
        if changed:
            self._refresh_render_order()
            self.object_tree.update_tree()
            self.statusbar.showMessage(f"Object reordered: {action}.")

    def _on_move_object_to_layer(self, obj_id: int, layer_id: int):
        from polycad.scene import Document
        doc = Document.instance()
        if not doc:
            return
        if doc.move_object_to_layer(obj_id, layer_id):
            L = doc.get_layer(layer_id)
            self._refresh_render_order()
            self.object_tree.update_tree()
            self.statusbar.showMessage(f"Moved object to {L.name if L else 'layer'}.")

    def _on_new_layer(self):
        from polycad.scene import Document
        doc = Document.instance()
        if not doc:
            return
        L = doc.create_layer()
        self._refresh_render_order()
        self.object_tree.update_tree()
        self.statusbar.showMessage(f"New layer added: {L.name} (active).")

    def _on_delete_layer(self, layer_id: int):
        from polycad.scene import Document
        doc = Document.instance()
        if not doc:
            return
        L = doc.get_layer(layer_id)
        if L is None:
            return
        if doc.delete_layer(layer_id):
            self._refresh_render_order()
            self.object_tree.update_tree()
            self.statusbar.showMessage(f"Deleted layer: {L.name} (objects merged).")
        else:
            self.statusbar.showMessage("Cannot delete the last remaining layer.")

    def _on_rename_layer(self, layer_id: int, new_name: str):
        from polycad.scene import Document
        doc = Document.instance()
        if not doc:
            return
        L = doc.get_layer(layer_id)
        if L is None:
            return
        L.name = new_name
        self.object_tree.update_tree()
        self.statusbar.showMessage(f"Layer renamed: {new_name}.")

    def _on_layer_visibility_toggled(self, layer_id: int):
        from polycad.scene import Document
        doc = Document.instance()
        if not doc:
            return
        L = doc.get_layer(layer_id)
        if L is None:
            return
        L.visible = not L.visible
        # If the currently selected object is in a now-hidden layer, deselect
        if not L.visible:
            for oid in list(doc.selected_ids):
                if oid in L._object_ids:
                    doc.deselect_all()
                    self.prop_panel.update_for_object(None)
                    self.gl_widget._deselect()
                    break
        self._refresh_render_order()
        self.object_tree.update_tree()
        self.statusbar.showMessage(
            f"Layer '{L.name}' is now {'visible' if L.visible else 'hidden'}."
        )

    def _on_layer_lock_toggled(self, layer_id: int):
        from polycad.scene import Document
        doc = Document.instance()
        if not doc:
            return
        L = doc.get_layer(layer_id)
        if L is None:
            return
        L.locked = not L.locked
        # If a now-locked layer holds the selection, drop the gizmo
        if L.locked:
            for oid in list(doc.selected_ids):
                if oid in L._object_ids:
                    self.gl_widget._deselect()
                    break
        self.object_tree.update_tree()
        self.statusbar.showMessage(
            f"Layer '{L.name}' is now {'locked' if L.locked else 'unlocked'}."
        )

    def _on_layer_move(self, direction: str, layer_id: int):
        from polycad.scene import Document
        doc = Document.instance()
        if not doc:
            return
        changed = (doc.move_layer_up(layer_id) if direction == "up"
                   else doc.move_layer_down(layer_id))
        if changed:
            self._refresh_render_order()
            self.object_tree.update_tree()
            self.statusbar.showMessage(f"Layer moved {direction}.")

    def _on_object_renamed(self, obj_id: int, new_name: str):
        """User finished an inline rename in the tree — refresh the
        property panel (so its title reflects the new name) and report."""
        from polycad.scene import Document
        doc = Document.instance()
        if not doc:
            return
        obj = doc.get_object_by_id(obj_id)
        if obj is None:
            return
        if obj.id in doc.selected_ids:
            sel = [doc.get_object_by_id(i) for i in doc.selected_ids]
            sel = [o for o in sel if o is not None]
            self.prop_panel.update_for_objects(sel)
        self.statusbar.showMessage(f"Renamed: {new_name}")

    def _on_active_layer_changed(self, layer_id: int):
        from polycad.scene import Document
        doc = Document.instance()
        if not doc:
            return
        doc.set_active_layer(layer_id)
        L = doc.get_layer(layer_id)
        self.object_tree.update_tree()
        if L:
            self.statusbar.showMessage(f"Active layer: {L.name}.")

    def closeEvent(self, event):
        """Clean up pyqtgraph items on close."""
        from polycad.scene import Document
        doc = Document.instance()
        if doc:
            self.gl_widget.clear_scene()
            Document.destroy_instance()
        super().closeEvent(event)

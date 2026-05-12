"""Toolbar with action buttons for common operations."""

from PySide6.QtWidgets import QPushButton, QWidget, QHBoxLayout, QLabel, QFrame


class Toolbar(QWidget):
    """Main toolbar with primitive creation and view controls.

    Uses a dark card-style background with grouped buttons and visual separators
    so buttons don't appear to float in empty space.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(48)
        self._setup_ui()

    def _setup_ui(self):
        self.setStyleSheet("""
            Toolbar {
                background-color: #181825;
                border-bottom: 1px solid #313244;
            }
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(4)

        # --- Primitives group ---
        layout.addWidget(self._make_section_label("Add"))

        prim_icons = {
            "Box": "⬜",
            "Cylinder": "⬡",
            "Sphere": "⬤",
            "Cone": "▲",
        }
        for text, icon in prim_icons.items():
            btn = QPushButton(f" {icon} {text}")
            btn.setFixedHeight(34)
            btn.setMinimumWidth(70)
            btn.setToolTip(f"Add {text}")
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #313244;
                    border: 1px solid #45475a;
                    border-radius: 6px;
                    padding: 2px 8px;
                    font-size: 9pt;
                }
                QPushButton:hover {
                    background-color: #45475a;
                    border-color: #89b4fa;
                }
                QPushButton:pressed {
                    background-color: #585b70;
                }
            """)
            setattr(self, f"_btn_{text.lower()}", btn)
            layout.addWidget(btn)

        # Vertical separator
        layout.addWidget(self._make_separator())

        # --- View group ---
        layout.addWidget(self._make_section_label("View"))

        self._btn_wireframe = QPushButton("🔲 Wire")
        self._btn_wireframe.setFixedHeight(34)
        self._btn_wireframe.setMinimumWidth(70)
        self._btn_wireframe.setCheckable(True)
        self._btn_wireframe.setToolTip("Toggle Wireframe (F)")
        self._btn_wireframe.setStyleSheet("""
            QPushButton {
                background-color: #313244;
                border: 1px solid #45475a;
                border-radius: 6px;
                padding: 2px 8px;
                font-size: 9pt;
            }
            QPushButton:hover {
                background-color: #45475a;
                border-color: #89b4fa;
            }
            QPushButton:checked {
                background-color: #89b4fa;
                color: #1e1e2e;
                border-color: #89b4fa;
                font-weight: bold;
            }
        """)
        layout.addWidget(self._btn_wireframe)

        # Spacer pushes delete to right edge
        layout.addStretch()

        # --- Delete button (right-aligned, distinct color) ---
        self._btn_delete = QPushButton("🗑 Delete")
        self._btn_delete.setFixedHeight(34)
        self._btn_delete.setMinimumWidth(80)
        self._btn_delete.setToolTip("Delete Selected (Del)")
        self._btn_delete.setStyleSheet("""
            QPushButton {
                background-color: #45273a;
                color: #f38ba8;
                border: 1px solid #f38ba8;
                border-radius: 6px;
                padding: 2px 10px;
                font-size: 9pt;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #f38ba8;
                color: #1e1e2e;
            }
            QPushButton:pressed {
                background-color: #eba0ac;
            }
        """)
        layout.addWidget(self._btn_delete)

    @staticmethod
    def _make_section_label(text: str) -> QLabel:
        """Create a styled section label for toolbar groups."""
        lbl = QLabel(text)
        lbl.setStyleSheet("""
            QLabel {
                color: #6c7086;
                font-weight: bold;
                font-size: 8pt;
                padding: 0 4px;
                background-color: transparent;
            }
        """)
        return lbl

    @staticmethod
    def _make_separator() -> QFrame:
        """Create a vertical line separator."""
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setFixedWidth(2)
        sep.setFixedHeight(28)
        sep.setStyleSheet("QFrame { color: #45475a; }")
        return sep


"""Object tree panel — QTreeView showing scene hierarchy with layers."""

from PySide6.QtWidgets import (
    QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget, QLabel, QPushButton,
    QHBoxLayout, QMenu, QInputDialog,
)
from PySide6.QtGui import (
    QColor, QAction, QIcon, QPixmap, QPainter, QFont as _QFont, QBrush, QPen,
)
from PySide6.QtWidgets import QHeaderView
from PySide6.QtCore import Qt, Signal

_ID_ROLE = Qt.ItemDataRole.UserRole         # Object id (for object rows)
_KIND_ROLE = Qt.ItemDataRole.UserRole + 1   # "layer" or "object"
_LAYER_ID_ROLE = Qt.ItemDataRole.UserRole + 2

# Maps the primitive's BaseObject.name to a glyph used as the row icon.
_TYPE_EMOJI = {"Box": "⬜", "Cylinder": "⬡", "Sphere": "⬤", "Cone": "▲"}

# Per-(emoji, color) icon cache so we don't repaint pixmaps on every refresh
_EMOJI_ICON_CACHE: dict = {}


def _emoji_icon(emoji: str, size: int = 18, color: str = "#cdd6f4") -> QIcon:
    """Render a geometric glyph as a tinted QIcon and cache it.

    The geometric Unicode symbols (⬜⬡⬤▲) render as monochrome glyphs that
    honour the painter's pen colour — so we tint each row's icon with the
    object's actual colour, giving the tree a per-row colour identity
    without needing a custom delegate."""
    key = f"{emoji}|{size}|{color}"
    cached = _EMOJI_ICON_CACHE.get(key)
    if cached is not None:
        return cached
    pix = QPixmap(size, size)
    pix.fill(Qt.GlobalColor.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
    f = _QFont("Segoe UI Emoji", int(size * 0.62))
    p.setFont(f)
    p.setPen(QColor(color))
    p.drawText(pix.rect(), int(Qt.AlignmentFlag.AlignCenter), emoji)
    p.end()
    icon = QIcon(pix)
    _EMOJI_ICON_CACHE[key] = icon
    return icon


def _color_swatch_icon(rgb, size: int = 14, radius: int = 3) -> QIcon:
    """Small rounded-rect colour chip used in the type column."""
    pix = QPixmap(size, size)
    pix.fill(Qt.GlobalColor.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setBrush(QBrush(QColor.fromRgbF(float(rgb[0]), float(rgb[1]), float(rgb[2]))))
    p.setPen(QPen(QColor("#45475a"), 1))
    p.drawRoundedRect(1, 1, size - 2, size - 2, radius, radius)
    p.end()
    return QIcon(pix)


def _rgb_to_hex(rgb) -> str:
    return "#{:02x}{:02x}{:02x}".format(
        max(0, min(255, int(float(rgb[0]) * 255))),
        max(0, min(255, int(float(rgb[1]) * 255))),
        max(0, min(255, int(float(rgb[2]) * 255))),
    )


class ObjectTreePanel(QWidget):
    """Tree widget displaying layers as root and objects as children.

    Layers are listed top→bottom in the tree as front→back (so the
    topmost row visually corresponds to the frontmost layer, matching
    Photoshop / Illustrator conventions).
    """

    # Signals consumed by MainWindow
    object_reorder_requested = Signal(str, int)         # action, obj_id
    move_object_to_layer_requested = Signal(int, int)   # obj_id, layer_id
    new_layer_requested = Signal()
    delete_layer_requested = Signal(int)                # layer_id
    rename_layer_requested = Signal(int, str)           # layer_id, new_name
    layer_visibility_toggled = Signal(int)              # layer_id
    layer_lock_toggled = Signal(int)                    # layer_id
    layer_move_requested = Signal(str, int)             # "up"/"down", layer_id
    active_layer_changed = Signal(int)                  # layer_id
    selection_changed_multi = Signal(list)              # list[int] of selected obj IDs
    object_renamed = Signal(int, str)                   # obj_id, new_display_name

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumWidth(180)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Panel header with "+ Layer" button
        header_row = QWidget()
        header_row.setFixedHeight(32)
        header_row.setStyleSheet("""
            QWidget {
                background-color: #181825;
                border-bottom: 1px solid #313244;
            }
        """)
        h_layout = QHBoxLayout(header_row)
        h_layout.setContentsMargins(8, 0, 4, 0)
        h_layout.setSpacing(4)
        title = QLabel("📁  Scene")
        title.setStyleSheet("""
            QLabel {
                color: #a6adc8;
                font-weight: bold;
                font-size: 9pt;
                background-color: transparent;
                border: none;
            }
        """)
        h_layout.addWidget(title)
        h_layout.addStretch()
        self._btn_new_layer = QPushButton("+ Layer")
        self._btn_new_layer.setFixedHeight(22)
        self._btn_new_layer.setStyleSheet("""
            QPushButton {
                background-color: #313244;
                color: #cdd6f4;
                border: 1px solid #45475a;
                border-radius: 4px;
                padding: 0 8px;
                font-size: 8pt;
            }
            QPushButton:hover {
                background-color: #45475a;
                border-color: #89b4fa;
            }
        """)
        self._btn_new_layer.clicked.connect(self.new_layer_requested.emit)
        h_layout.addWidget(self._btn_new_layer)
        layout.addWidget(header_row)

        # Tree widget
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Name", ""])
        self.tree.setSelectionMode(QTreeWidget.SelectionMode.ExtendedSelection)
        self.tree.setColumnCount(2)
        self.tree.setRootIsDecorated(True)
        self.tree.setIndentation(14)
        self.tree.setAnimated(True)
        self.tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.tree.header().setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        self.tree.header().resizeSection(1, 44)
        from PySide6.QtCore import QSize
        self.tree.setIconSize(QSize(18, 18))
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._show_context_menu)
        self.tree.setStyleSheet("""
            QTreeWidget {
                border: none;
                border-radius: 0;
                background-color: #1e1e2e;
                outline: none;
            }
            QTreeWidget::item {
                padding: 4px 6px;
                border-radius: 0;
            }
            QTreeWidget::item:selected {
                background-color: #313244;
                color: #89b4fa;
                border-left: 3px solid #89b4fa;
            }
            QTreeWidget::item:hover:!selected {
                background-color: #24243a;
            }
            QHeaderView::section {
                background-color: #181825;
                color: #6c7086;
                border: none;
                border-bottom: 1px solid #313244;
                padding: 3px 8px;
                font-size: 8pt;
                font-weight: bold;
            }
        """)
        self.tree.itemClicked.connect(self._on_item_clicked)
        self.tree.itemSelectionChanged.connect(self._on_selection_changed)
        self.tree.itemChanged.connect(self._on_item_changed)
        layout.addWidget(self.tree)

    # ------------------------------------------------------------------ #
    #  Build / refresh
    # ------------------------------------------------------------------ #

    def update_tree(self):
        """Full rebuild — cheap enough for layer-counts we expect.

        Object rows show: [tinted type glyph] [editable display_name]
        | [rounded colour swatch]. Layer rows keep their text-based layout
        (active dot, visibility, name, lock) since they're renamed via a
        dialog rather than inline."""
        from polycad.scene import Document
        doc = Document.instance()
        if not doc:
            return

        self.tree.blockSignals(True)
        self.tree.clear()

        # Display layers top→bottom = front→back (reverse of internal order)
        for L in reversed(doc.get_layers()):
            layer_item = QTreeWidgetItem()
            layer_item.setData(0, _KIND_ROLE, "layer")
            layer_item.setData(0, _LAYER_ID_ROLE, L.id)
            # Layers are NOT inline-editable — keep flags free of ItemIsEditable
            layer_item.setFlags(layer_item.flags() & ~Qt.ItemFlag.ItemIsEditable)

            is_active = (L.id == doc._active_layer_id)
            vis_icon = "👁" if L.visible else "—"
            lock_icon = "🔒" if L.locked else ""
            active_marker = "● " if is_active else "  "
            layer_item.setText(0, f"{active_marker}{vis_icon} {L.name} {lock_icon}".rstrip())
            layer_item.setText(1, f"[{len(L._object_ids)}]")
            layer_item.setForeground(0, QColor("#cdd6f4" if is_active else "#a6adc8"))
            layer_item.setForeground(1, QColor("#6c7086"))

            # Children: objects, displayed front→back as well
            for oid in reversed(L._object_ids):
                obj = doc.get_object_by_id(oid)
                if obj is None:
                    continue
                child = QTreeWidgetItem()
                child.setData(0, _KIND_ROLE, "object")
                child.setData(0, _ID_ROLE, obj.id)
                # Inline rename: double-click / F2 / right-click "Rename"
                child.setFlags(child.flags() | Qt.ItemFlag.ItemIsEditable)

                display_name = getattr(obj, '_display_name', None) or obj.name
                child.setText(0, display_name)

                # Tint the glyph with the object's own colour so each row
                # carries a visual identity even before the swatch column.
                emoji = _TYPE_EMOJI.get(obj.name, "◆")
                tint = _rgb_to_hex(obj.color) if L.visible else "#585b70"
                child.setIcon(0, _emoji_icon(emoji, color=tint))

                # Swatch in col 1 — no text, just a coloured chip
                child.setIcon(1, _color_swatch_icon(
                    (float(obj.color[0]), float(obj.color[1]), float(obj.color[2]))
                ))
                child.setText(1, "")
                child.setToolTip(0, f"{display_name}  ({obj.name})")
                child.setToolTip(1, f"Type: {obj.name}")

                if not L.visible:
                    child.setForeground(0, QColor("#585b70"))
                child.setSelected(obj.selected)
                layer_item.addChild(child)

            self.tree.addTopLevelItem(layer_item)
            layer_item.setExpanded(True)

        self.tree.blockSignals(False)

    # ------------------------------------------------------------------ #
    #  Click handling
    # ------------------------------------------------------------------ #

    def _on_item_clicked(self, item, column=0):
        """Only handle layer activation here. Object-selection is driven by
        `_on_selection_changed` (fires for every multi-select change)."""
        kind = item.data(0, _KIND_ROLE)
        if kind == "layer":
            layer_id = item.data(0, _LAYER_ID_ROLE)
            if layer_id is not None:
                self.active_layer_changed.emit(layer_id)

    def _on_selection_changed(self):
        """Qt tree multi-selection changed — emit the full list of selected
        object IDs (layers are ignored). MainWindow drives Document from this."""
        from polycad.scene import Document
        doc = Document.instance()
        if not doc:
            return
        ids: list[int] = []
        for item in self.tree.selectedItems():
            if item.data(0, _KIND_ROLE) == "object":
                oid = item.data(0, _ID_ROLE)
                if oid is not None:
                    ids.append(int(oid))
        # If the user has at least one object selected, also bump that
        # object's layer to active so the next primitive lands there.
        if ids:
            L = doc._find_layer_of(ids[-1])
            if L is not None and doc._active_layer_id != L.id:
                doc.set_active_layer(L.id)
        self.selection_changed_multi.emit(ids)

    def _on_item_changed(self, item, column):
        """Inline rename for object rows. Fires when the user finishes
        editing a tree item; we only care about column 0 of object rows."""
        if column != 0:
            return
        if item.data(0, _KIND_ROLE) != "object":
            return
        obj_id = item.data(0, _ID_ROLE)
        if obj_id is None:
            return
        from polycad.scene import Document
        doc = Document.instance()
        if not doc:
            return
        obj = doc.get_object_by_id(int(obj_id))
        if obj is None:
            return
        new_text = item.text(0).strip()
        if not new_text:
            # Empty rename — revert to whatever the object currently knows
            self.tree.blockSignals(True)
            item.setText(0, getattr(obj, '_display_name', None) or obj.name)
            self.tree.blockSignals(False)
            return
        prev = getattr(obj, '_display_name', None) or obj.name
        if prev == new_text:
            return
        obj._display_name = new_text
        self.object_renamed.emit(int(obj_id), new_text)

    # ------------------------------------------------------------------ #
    #  Context menu
    # ------------------------------------------------------------------ #

    def _show_context_menu(self, point):
        item = self.tree.itemAt(point)
        if item is None:
            menu = QMenu(self)
            act_new = QAction("+ New Layer", self)
            act_new.triggered.connect(self.new_layer_requested.emit)
            menu.addAction(act_new)
            menu.exec(self.tree.viewport().mapToGlobal(point))
            return

        kind = item.data(0, _KIND_ROLE)
        menu = QMenu(self)

        if kind == "object":
            obj_id = item.data(0, _ID_ROLE)

            a_rename = QAction("Rename  (F2)", self)
            a_rename.triggered.connect(lambda _=False, it=item: self.tree.editItem(it, 0))
            menu.addAction(a_rename)
            menu.addSeparator()

            for label, action in (
                ("Bring to Front",  "front"),
                ("Bring Forward",   "forward"),
                ("Send Backward",   "backward"),
                ("Send to Back",    "back"),
            ):
                a = QAction(label, self)
                a.triggered.connect(lambda _=False, ac=action, oid=obj_id:
                                    self.object_reorder_requested.emit(ac, oid))
                menu.addAction(a)

            # "Move to Layer →" submenu
            from polycad.scene import Document
            doc = Document.instance()
            if doc:
                menu.addSeparator()
                move_menu = menu.addMenu("Move to Layer")
                cur_layer = doc._find_layer_of(obj_id)
                for L in reversed(doc.get_layers()):
                    a = QAction(L.name + ("  (current)" if cur_layer and L.id == cur_layer.id else ""), self)
                    a.setEnabled(not (cur_layer and L.id == cur_layer.id))
                    a.triggered.connect(lambda _=False, oid=obj_id, lid=L.id:
                                        self.move_object_to_layer_requested.emit(oid, lid))
                    move_menu.addAction(a)

        elif kind == "layer":
            layer_id = item.data(0, _LAYER_ID_ROLE)
            from polycad.scene import Document
            doc = Document.instance()
            L = doc.get_layer(layer_id) if doc else None

            a_vis = QAction("Hide Layer" if (L and L.visible) else "Show Layer", self)
            a_vis.triggered.connect(lambda: self.layer_visibility_toggled.emit(layer_id))
            menu.addAction(a_vis)

            a_lock = QAction("Unlock Layer" if (L and L.locked) else "Lock Layer", self)
            a_lock.triggered.connect(lambda: self.layer_lock_toggled.emit(layer_id))
            menu.addAction(a_lock)

            menu.addSeparator()

            a_up = QAction("Move Layer Up", self)
            a_up.triggered.connect(lambda: self.layer_move_requested.emit("up", layer_id))
            menu.addAction(a_up)
            a_dn = QAction("Move Layer Down", self)
            a_dn.triggered.connect(lambda: self.layer_move_requested.emit("down", layer_id))
            menu.addAction(a_dn)

            menu.addSeparator()

            a_rename = QAction("Rename...", self)
            def do_rename():
                old = L.name if L else ""
                new, ok = QInputDialog.getText(self, "Rename Layer", "Name:", text=old)
                if ok and new.strip():
                    self.rename_layer_requested.emit(layer_id, new.strip())
            a_rename.triggered.connect(do_rename)
            menu.addAction(a_rename)

            a_del = QAction("Delete Layer", self)
            a_del.triggered.connect(lambda: self.delete_layer_requested.emit(layer_id))
            menu.addAction(a_del)

            menu.addSeparator()
            a_new = QAction("+ New Layer", self)
            a_new.triggered.connect(self.new_layer_requested.emit)
            menu.addAction(a_new)

        menu.exec(self.tree.viewport().mapToGlobal(point))

    def get_selected_object(self):
        """Get the currently selected object or None."""
        from polycad.scene import Document
        doc = Document.instance()
        if not doc:
            return None
        item = self.tree.currentItem()
        if item is None or item.data(0, _KIND_ROLE) != "object":
            return None
        object_id = item.data(0, _ID_ROLE)
        if object_id is not None:
            return doc.get_object_by_id(object_id)
        return None


"""Property panel — editor for selected object properties."""

import math
from PySide6.QtWidgets import (
    QFormLayout, QLineEdit, QPushButton, QVBoxLayout, QWidget, QLabel, QSpinBox,
    QDoubleSpinBox, QHBoxLayout, QColorDialog, QFrame,
)
from PySide6.QtGui import QColor
from PySide6.QtCore import Qt, Signal


class PropertyPanel(QWidget):
    """Panel for editing selected object properties.

    All 3 XYZ groups (Position, Rotation, Scale) are live-connected:
    changing any spinbox immediately updates the selected object's
    transform and pushes it to the GL viewport.
    """

    transform_changed = Signal(object)
    color_changed = Signal(object)
    # Carries a list of (obj, old_data, new_data) tuples so multi-edits batch
    # into a single undo entry in MainWindow.
    property_edit_finished = Signal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumWidth(220)
        self._current_obj = None          # Primary (last clicked) — drives display
        self._selected_objs: list = []    # All currently selected objects
        self._updating = False
        self._pending_old_datas: dict = {}   # obj_id -> ObjectData at edit start
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Panel header
        header = QLabel("  ⚙  Properties")
        header.setFixedHeight(32)
        header.setStyleSheet("""
            QLabel {
                background-color: #181825;
                color: #a6adc8;
                font-weight: bold;
                font-size: 9pt;
                border-bottom: 1px solid #313244;
                padding-left: 8px;
            }
        """)
        layout.addWidget(header)

        # Content area with padding
        content = QWidget()
        self._content_layout = QVBoxLayout(content)
        self._content_layout.setContentsMargins(10, 10, 10, 10)
        self._content_layout.setSpacing(6)

        # Object name
        self.name_label = QLabel("No object selected")
        self.name_label.setStyleSheet("""
            QLabel {
                color: #cdd6f4;
                font-size: 11pt;
                font-weight: bold;
                padding: 4px 0 8px 0;
            }
        """)
        self._content_layout.addWidget(self.name_label)

        # Thin separator
        self._content_layout.addWidget(self._make_hsep())

        def _add_spin_group(title, prefix, min_v, max_v, step, dec, suffix="", default=None):
            self._content_layout.addWidget(self._make_group_label(title))
            for axis, color in [("X", "#f38ba8"), ("Y", "#a6e3a1"), ("Z", "#89b4fa")]:
                row = QHBoxLayout()
                row.setContentsMargins(0, 0, 0, 0)
                row.setSpacing(6)
                lbl = QLabel(axis)
                lbl.setFixedSize(22, 28)
                lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
                lbl.setStyleSheet(f"QLabel {{ color: {color}; font-weight: bold; font-size: 9pt; background-color: #313244; border-radius: 4px; }}")
                spin = QDoubleSpinBox()
                spin.setMinimumHeight(28)
                spin.setRange(min_v, max_v)
                spin.setDecimals(dec)
                spin.setSingleStep(step)
                if suffix: spin.setSuffix(suffix)
                if default is not None: spin.setValue(default)
                spin.valueChanged.connect(self._on_value_changed)
                spin.editingFinished.connect(self._on_editing_finished)
                setattr(self, f"{prefix}_{axis.lower()}", spin)
                row.addWidget(lbl)
                row.addWidget(spin, 1)
                self._content_layout.addLayout(row)

        _add_spin_group("📍 Position", "pos", -999.0, 999.0, 0.1, 2)
        _add_spin_group("🔄 Rotation", "rot", -360.0, 360.0, 5.0, 1, suffix="°")
        _add_spin_group("📐 Scale", "scale", 0.01, 99.0, 0.1, 2, default=1.0)

        # Separator
        self._content_layout.addWidget(self._make_hsep())

        # Color section
        self._content_layout.addWidget(self._make_group_label("🎨 Color"))
        color_row = QWidget()
        color_layout = QHBoxLayout(color_row)
        color_layout.setContentsMargins(0, 0, 0, 0)

        self.color_btn = QPushButton("")
        self.color_btn.setFixedSize(36, 28)
        self.color_btn.setStyleSheet("""
            QPushButton {
                background-color: #666;
                border: 2px solid #45475a;
                border-radius: 6px;
            }
            QPushButton:hover {
                border-color: #89b4fa;
            }
        """)
        self.color_btn.clicked.connect(self._on_color_click)

        self.color_label = QLabel("Pick a color")
        self.color_label.setStyleSheet("QLabel { color: #6c7086; font-size: 9pt; }")

        color_layout.addWidget(self.color_btn)
        color_layout.addWidget(self.color_label)
        color_layout.addStretch()
        self._content_layout.addWidget(color_row)

        # Push everything up
        self._content_layout.addStretch()
        layout.addWidget(content)

    # ------------------------------------------------------------------ #
    #  Helpers
    # ------------------------------------------------------------------ #

    @staticmethod
    def _make_group_label(text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet("""
            QLabel {
                color: #a6adc8;
                font-size: 9pt;
                font-weight: bold;
                padding: 6px 0 2px 0;
                background-color: transparent;
            }
        """)
        return lbl

    @staticmethod
    def _make_hsep() -> QFrame:
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setFixedHeight(1)
        sep.setStyleSheet("QFrame { color: #313244; }")
        return sep

    # ------------------------------------------------------------------ #
    #  Populate panel from an object
    # ------------------------------------------------------------------ #

    def update_for_object(self, obj):
        """Backward-compatible single-object update; delegates to multi."""
        self.update_for_objects([obj] if obj is not None else [])

    def update_for_objects(self, objs):
        """Update panel to reflect a (possibly multi-) object selection.

        The PRIMARY object (last item in `objs`) drives the displayed values.
        When the user edits a spinbox we will apply the same *delta* (or
        ratio, for scale) to every selected object, so each one rotates /
        moves / scales around its own current state — matching Blender's
        multi-edit behaviour.
        """
        self._selected_objs = list(objs)
        self._current_obj = objs[-1] if objs else None

        if not objs:
            self.name_label.setText("No object selected")
            self.color_btn.setStyleSheet("""
                QPushButton {
                    background-color: #666;
                    border: 2px solid #45475a;
                    border-radius: 6px;
                }
            """)
            self.color_label.setText("Pick a color")
            return

        from polycad.scene import BaseObject
        obj = self._current_obj
        if not isinstance(obj, BaseObject):
            return

        self._updating = True

        if len(objs) > 1:
            self.name_label.setText(f"{len(objs)} objects selected")
        else:
            display_name = getattr(obj, '_display_name', None) or obj.name
            self.name_label.setText(display_name)

        # Position
        for i, axis in enumerate("xyz"):
            spin = getattr(self, f"pos_{axis}")
            spin.setValue(float(obj.position[i]))

        # Rotation (radians → degrees)
        for i, axis in enumerate("xyz"):
            spin = getattr(self, f"rot_{axis}")
            spin.setValue(math.degrees(float(obj.rotation_euler[i])))

        # Scale
        for i, axis in enumerate("xyz"):
            spin = getattr(self, f"scale_{axis}")
            spin.setValue(float(obj.scale[i]))

        # Color button
        color_hex = (
            f"#{int(obj.color[0]*255):02x}"
            f"{int(obj.color[1]*255):02x}"
            f"{int(obj.color[2]*255):02x}"
        )
        self.color_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {color_hex};
                border: 2px solid #45475a;
                border-radius: 6px;
            }}
            QPushButton:hover {{
                border-color: #89b4fa;
            }}
        """)
        self.color_label.setText(color_hex)

        self._updating = False

    # ------------------------------------------------------------------ #
    #  Live-edit handler
    # ------------------------------------------------------------------ #

    def _on_value_changed(self):
        if self._updating or self._current_obj is None:
            return
        # First change in this edit session: snapshot every selected obj's
        # state so we can compute consistent deltas as the spinbox moves.
        if not self._pending_old_datas:
            for o in self._selected_objs:
                self._pending_old_datas[o.id] = o.to_data()

        self.apply_changes()
        self.transform_changed.emit(self._current_obj)

    def _on_editing_finished(self):
        """Spinbox edit session ended — emit one batch with every changed
        object so MainWindow can record it as a single undo entry."""
        if not self._pending_old_datas:
            return
        edits: list = []
        for o in self._selected_objs:
            old = self._pending_old_datas.get(o.id)
            if old is None:
                continue
            new = o.to_data()
            if old.model_dump() != new.model_dump():
                edits.append((o, old, new))
        if edits:
            self.property_edit_finished.emit(edits)
        self._pending_old_datas = {}

    # ------------------------------------------------------------------ #
    #  Write spin-box values → object(s)
    # ------------------------------------------------------------------ #

    def apply_changes(self):
        """Apply spinbox values to the selection.

        Single selection: write spinboxes directly to the primary.
        Multi-selection : compute (new - primary_old) deltas for position
        and rotation, and (new / primary_old) ratios for scale, then push
        the same delta/ratio onto every selected object's *starting* state.
        That way each object stays in its own neighbourhood while moving
        together by the amount the user dialled in.
        """
        primary = self._current_obj
        if primary is None:
            return
        from polycad.scene import BaseObject
        if not isinstance(primary, BaseObject):
            return

        # Read spinbox state (panel is showing primary's values)
        new_pos = tuple(getattr(self, f"pos_{a}").value()   for a in "xyz")
        new_rot = tuple(getattr(self, f"rot_{a}").value()   for a in "xyz")  # degrees
        new_scl = tuple(getattr(self, f"scale_{a}").value() for a in "xyz")

        if len(self._selected_objs) <= 1:
            # Single — direct write
            for i in range(3):
                primary.position[i]       = new_pos[i]
                primary.rotation_euler[i] = math.radians(new_rot[i])
                primary.scale[i]          = max(0.01, new_scl[i])
            return

        # Multi-select — delta/ratio from primary's snapshot
        prim_old = self._pending_old_datas.get(primary.id)
        if prim_old is None:
            # No snapshot yet (shouldn't happen because _on_value_changed
            # snapshots first), but degrade gracefully to single-mode.
            for i in range(3):
                primary.position[i]       = new_pos[i]
                primary.rotation_euler[i] = math.radians(new_rot[i])
                primary.scale[i]          = max(0.01, new_scl[i])
            return

        d_pos = tuple(new_pos[i] - prim_old.position[i] for i in range(3))
        d_rot = tuple(new_rot[i] - prim_old.rotation[i] for i in range(3))  # degrees
        s_scl = tuple(
            (new_scl[i] / prim_old.scale[i]) if prim_old.scale[i] else 1.0
            for i in range(3)
        )

        for o in self._selected_objs:
            old = self._pending_old_datas.get(o.id)
            if old is None:
                continue
            for i in range(3):
                o.position[i]       = old.position[i] + d_pos[i]
                o.rotation_euler[i] = math.radians(old.rotation[i] + d_rot[i])
                o.scale[i]          = max(0.01, old.scale[i] * s_scl[i])

    # ------------------------------------------------------------------ #
    #  Color picker
    # ------------------------------------------------------------------ #

    def _on_color_click(self):
        primary = self._current_obj
        if primary is None:
            return

        qt_color = QColor(
            int(primary.color[0] * 255),
            int(primary.color[1] * 255),
            int(primary.color[2] * 255),
        )
        selected = QColorDialog.getColor(qt_color, self, "Select Color")
        if not selected.isValid():
            return

        # Apply the picked colour to every selected object
        edits: list = []
        targets = self._selected_objs or [primary]
        for o in targets:
            old_data = o.to_data()
            o.set_color(selected.redF(), selected.greenF(), selected.blueF())
            new_data = o.to_data()
            if old_data.model_dump() != new_data.model_dump():
                edits.append((o, old_data, new_data))
            self.color_changed.emit(o)

        if edits:
            self.property_edit_finished.emit(edits)

        color_hex = selected.name()
        self.color_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {color_hex};
                border: 2px solid #45475a;
                border-radius: 6px;
            }}
            QPushButton:hover {{
                border-color: #89b4fa;
            }}
        """)
        self.color_label.setText(color_hex)



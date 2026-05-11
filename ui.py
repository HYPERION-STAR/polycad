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


"""Object tree panel — QTreeView showing scene hierarchy."""

from PySide6.QtWidgets import (
    QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget, QLabel,
)
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QHeaderView
from PySide6.QtCore import Qt

_ID_ROLE = Qt.ItemDataRole.UserRole  # Dedicated role for object ID storage


class ObjectTreePanel(QWidget):
    """Tree widget displaying the scene object hierarchy."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumWidth(160)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Panel header
        header = QLabel("  📁  Scene Objects")
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

        # Tree widget
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Name", "Type"])
        self.tree.setSelectionMode(QTreeWidget.SelectionMode.SingleSelection)
        self.tree.setColumnCount(2)
        self.tree.setRootIsDecorated(False)
        self.tree.setIndentation(8)
        self.tree.setAnimated(True)
        self.tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.tree.header().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.tree.setStyleSheet("""
            QTreeWidget {
                border: none;
                border-radius: 0;
                background-color: #1e1e2e;
                outline: none;
            }
            QTreeWidget::item {
                padding: 5px 8px;
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
        layout.addWidget(self.tree)

    def update_tree(self):
        """Refresh the tree dynamically to reflect current scene state without full rebuilds."""
        from polycad.scene import Document
        doc = Document.instance()
        if not doc:
            return

        icons = {"Box": "⬜", "Cylinder": "⬡", "Sphere": "⬤", "Cone": "▲"}
        
        # Track existing items
        existing_items = {}
        for i in range(self.tree.topLevelItemCount()):
            item = self.tree.topLevelItem(i)
            existing_items[item.data(0, _ID_ROLE)] = item

        # Sync items
        new_items = []
        for obj in doc.get_all_objects():
            if obj.id in existing_items:
                item = existing_items.pop(obj.id)
            else:
                item = QTreeWidgetItem()
                item.setData(0, _ID_ROLE, obj.id)
                new_items.append(item)
                
            icon = icons.get(obj.name, "◆")
            display_name = getattr(obj, '_display_name', None) or obj.name
            item.setText(0, f" {icon}  {display_name}")
            item.setText(1, obj.name)
            
            # Sync selection
            item.setSelected(obj.selected)

        # Add new items
        if new_items:
            self.tree.addTopLevelItems(new_items)
            
        # Remove deleted items
        for item in existing_items.values():
            index = self.tree.indexOfTopLevelItem(item)
            if index >= 0:
                self.tree.takeTopLevelItem(index)

    def _on_item_clicked(self, item):
        """Handle tree item selection — update document selection."""
        from polycad.scene import Document
        doc = Document.instance()
        if not doc:
            return

        object_id = item.data(0, _ID_ROLE)
        if object_id is not None:
            doc.selected_ids = {object_id}

    def get_selected_object(self):
        """Get the currently selected object or None."""
        from polycad.scene import Document
        doc = Document.instance()
        if not doc:
            return None
        item = self.tree.currentItem()
        if item is None:
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
    property_edit_finished = Signal(object, object, object)  # obj, old_data, new_data

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumWidth(220)
        self._current_obj = None
        self._updating = False
        self._pending_old_data = None
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
        """Update panel to reflect the given object's current state."""
        self._current_obj = obj

        if obj is None:
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
        if not isinstance(obj, BaseObject):
            return

        self._updating = True

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
        if self._pending_old_data is None:
            self._pending_old_data = self._current_obj.to_data()
            
        self.apply_changes()
        self.transform_changed.emit(self._current_obj)

    def _on_editing_finished(self):
        if self._pending_old_data is not None and self._current_obj is not None:
            new_data = self._current_obj.to_data()
            if self._pending_old_data.model_dump() != new_data.model_dump():
                self.property_edit_finished.emit(self._current_obj, self._pending_old_data, new_data)
            self._pending_old_data = None

    # ------------------------------------------------------------------ #
    #  Write spin-box values → object
    # ------------------------------------------------------------------ #

    def apply_changes(self):
        """Apply current panel values to the selected object."""
        obj = self._current_obj
        if obj is None:
            return

        from polycad.scene import BaseObject
        if not isinstance(obj, BaseObject):
            return

        for i, axis in enumerate("xyz"):
            spin = getattr(self, f"pos_{axis}")
            obj.position[i] = spin.value()

        for i, axis in enumerate("xyz"):
            spin = getattr(self, f"rot_{axis}")
            obj.rotation_euler[i] = math.radians(spin.value())

        for i, axis in enumerate("xyz"):
            spin = getattr(self, f"scale_{axis}")
            obj.scale[i] = max(0.01, spin.value())

    # ------------------------------------------------------------------ #
    #  Color picker
    # ------------------------------------------------------------------ #

    def _on_color_click(self):
        obj = self._current_obj
        if obj is None:
            return

        qt_color = QColor(
            int(obj.color[0] * 255),
            int(obj.color[1] * 255),
            int(obj.color[2] * 255),
        )
        selected = QColorDialog.getColor(qt_color, self, "Select Color")

        if selected.isValid():
            old_data = obj.to_data()
            obj.set_color(selected.redF(), selected.greenF(), selected.blueF())
            new_data = obj.to_data()
            
            if old_data.model_dump() != new_data.model_dump():
                self.property_edit_finished.emit(obj, old_data, new_data)
                
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
            self.color_changed.emit(obj)



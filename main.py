import os
import sys

def main():
    _project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if _project_root not in sys.path:
        sys.path.insert(0, _project_root)
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QGuiApplication
    QGuiApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    from PySide6.QtWidgets import QApplication
    app = QApplication(sys.argv)
    app.setApplicationName("PolyCAD")
    app.setOrganizationName("polycad")
    app.setStyleSheet(_get_stylesheet())
    from polycad.window import MainWindow
    window = MainWindow()
    window.show()
    sys.exit(app.exec())

def _get_stylesheet() -> str:
    _icons_dir = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "icons"
    ).replace("\\", "/")
    _arrow_up = f"{_icons_dir}/arrow_up.png"
    _arrow_down = f"{_icons_dir}/arrow_down.png"
    css = """
    /* ===== Global ===== */
    QWidget {
        background-color: #1e1e2e;
        color: #cdd6f4;
        font-family: "Segoe UI", "Inter", sans-serif;
        font-size: 10pt;
    }
    /* ===== Main Window ===== */
    QMainWindow {
        background-color: #1e1e2e;
    }
    /* ===== Menu Bar ===== */
    QMenuBar {
        background-color: #181825;
        color: #cdd6f4;
        border-bottom: 1px solid #313244;
        padding: 2px 0;
    }
    QMenuBar::item {
        padding: 4px 12px;
        border-radius: 4px;
    }
    QMenuBar::item:selected {
        background-color: #45475a;
    }
    QMenu {
        background-color: #1e1e2e;
        border: 1px solid #313244;
        border-radius: 6px;
        padding: 4px;
    }
    QMenu::item {
        padding: 6px 28px 6px 12px;
        border-radius: 4px;
    }
    QMenu::item:selected {
        background-color: #45475a;
    }
    QMenu::separator {
        height: 1px;
        background: #313244;
        margin: 4px 8px;
    }
    /* ===== Status Bar ===== */
    QStatusBar {
        background-color: #181825;
        color: #a6adc8;
        border-top: 1px solid #313244;
        font-size: 9pt;
    }
    QStatusBar QLabel {
        color: #a6adc8;
        padding: 0 8px;
        background-color: transparent;
    }
    /* ===== Splitter ===== */
    QSplitter::handle {
        background-color: #313244;
        width: 2px;
    }
    QSplitter::handle:hover {
        background-color: #89b4fa;
    }
    /* ===== Push Buttons (toolbar & general) ===== */
    QPushButton {
        background-color: #313244;
        color: #cdd6f4;
        border: 1px solid #45475a;
        border-radius: 6px;
        padding: 4px 10px;
        font-weight: 500;
    }
    QPushButton:hover {
        background-color: #45475a;
        border-color: #89b4fa;
    }
    QPushButton:pressed {
        background-color: #585b70;
    }
    QPushButton:checked {
        background-color: #89b4fa;
        color: #1e1e2e;
        border-color: #89b4fa;
    }
    /* ===== Spin Boxes ===== */
    QDoubleSpinBox, QSpinBox {
        background-color: #313244;
        color: #cdd6f4;
        border: 1px solid #45475a;
        border-radius: 4px;
        padding: 4px 22px 4px 8px;
        min-height: 24px;
        font-size: 10pt;
        selection-background-color: #89b4fa;
        selection-color: #1e1e2e;
    }
    QDoubleSpinBox:focus, QSpinBox:focus {
        border-color: #89b4fa;
    }
    /* Up button */
    QDoubleSpinBox::up-button, QSpinBox::up-button {
        subcontrol-origin: border;
        subcontrol-position: top right;
        background-color: #45475a;
        border: none;
        border-left: 1px solid #313244;
        border-top-right-radius: 4px;
        width: 20px;
    }
    QDoubleSpinBox::up-button:hover, QSpinBox::up-button:hover {
        background-color: #585b70;
    }
    QDoubleSpinBox::up-arrow, QSpinBox::up-arrow {
        image: url(%%ARROW_UP%%);
        width: 10px;
        height: 6px;
    }
    /* Down button */
    QDoubleSpinBox::down-button, QSpinBox::down-button {
        subcontrol-origin: border;
        subcontrol-position: bottom right;
        background-color: #45475a;
        border: none;
        border-left: 1px solid #313244;
        border-bottom-right-radius: 4px;
        width: 20px;
    }
    QDoubleSpinBox::down-button:hover, QSpinBox::down-button:hover {
        background-color: #585b70;
    }
    QDoubleSpinBox::down-arrow, QSpinBox::down-arrow {
        image: url(%%ARROW_DOWN%%);
        width: 10px;
        height: 6px;
    }
    /* ===== Tree Widget (Scene Objects) ===== */
    QTreeWidget {
        background-color: #1e1e2e;
        alternate-background-color: #181825;
        border: 1px solid #313244;
        border-radius: 6px;
        outline: none;
    }
    QTreeWidget::item {
        padding: 4px 6px;
        border-radius: 3px;
    }
    QTreeWidget::item:selected {
        background-color: #89b4fa;
        color: #1e1e2e;
    }
    QTreeWidget::item:hover {
        background-color: #313244;
    }
    QHeaderView::section {
        background-color: #181825;
        color: #a6adc8;
        border: none;
        border-bottom: 1px solid #313244;
        padding: 4px 8px;
        font-weight: bold;
        font-size: 9pt;
    }
    /* ===== Labels ===== */
    QLabel {
        background-color: transparent;
        color: #cdd6f4;
    }
    /* ===== Scroll Bars ===== */
    QScrollBar:vertical {
        background: #1e1e2e;
        width: 8px;
        border-radius: 4px;
    }
    QScrollBar::handle:vertical {
        background: #45475a;
        border-radius: 4px;
        min-height: 20px;
    }
    QScrollBar::handle:vertical:hover {
        background: #585b70;
    }
    QScrollBar::add-line, QScrollBar::sub-line {
        height: 0;
    }
    /* ===== Tooltips ===== */
    QToolTip {
        background-color: #313244;
        color: #cdd6f4;
        border: 1px solid #45475a;
        border-radius: 4px;
        padding: 4px 8px;
    }
    """
    css = css.replace("%%ARROW_UP%%", _arrow_up)
    css = css.replace("%%ARROW_DOWN%%", _arrow_down)
    return css
if __name__ == "__main__":
    main()
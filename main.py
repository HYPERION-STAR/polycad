import os
import sys

def main():
    _project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if _project_root not in sys.path:
        sys.path.insert(0, _project_root)
    from PySide6.QtCore import Qt, QTimer, QElapsedTimer
    from PySide6.QtGui import QGuiApplication, QFont, QColor, QIcon
    QGuiApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    from PySide6.QtWidgets import QApplication, QSplashScreen

    # On Windows, set an explicit AppUserModelID before QApplication starts
    # so the taskbar shows our icon as a distinct PolyCAD entry instead of
    # grouping under the generic python.exe icon. No-op on Linux/macOS.
    try:
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("polycad.app.1")
    except (AttributeError, OSError):
        pass

    app = QApplication(sys.argv)
    app.setApplicationName("PolyCAD")
    app.setOrganizationName("polycad")

    # Window / taskbar icon (eye image from icons/)
    _icon_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "icons", "13209590_black-weiss-eye.jpg",
    )
    if os.path.exists(_icon_path):
        app_icon = QIcon(_icon_path)
        app.setWindowIcon(app_icon)

    # Font fallback so emoji/symbol glyphs (⬜⬡⬤▲🔲🗑📁⚙📍🔄📐🎨) render on Windows
    QFont.insertSubstitutions("Segoe UI", ["Segoe UI Emoji", "Segoe UI Symbol"])
    QFont.insertSubstitutions("Inter",    ["Segoe UI Emoji", "Segoe UI Symbol"])
    base_font = QFont("Segoe UI", 10)
    base_font.setStyleStrategy(QFont.StyleStrategy.PreferDefault)
    app.setFont(base_font)

    app.setStyleSheet(_get_stylesheet())

    # ---- Splash screen (Photoshop-style intro) -----------------------
    splash_pix = _create_splash_pixmap()
    splash = QSplashScreen(splash_pix, Qt.WindowType.WindowStaysOnTopHint)
    splash.show()
    app.processEvents()

    def _phase(text: str):
        """Update the bottom-right status text on the splash."""
        splash.showMessage(
            text,
            int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignBottom),
            QColor("#a6adc8"),
        )
        app.processEvents()

    elapsed = QElapsedTimer()
    elapsed.start()

    _phase("  Initializing engine…    ")
    from polycad.window import MainWindow
    _phase("  Building viewport…    ")
    window = MainWindow()
    _phase("  Ready.    ")

    # Keep splash visible at least ~1.4s so the intro is perceivable
    remaining = max(0, 1400 - elapsed.elapsed())

    def _finish():
        window.show()
        splash.finish(window)

    QTimer.singleShot(remaining, _finish)
    sys.exit(app.exec())


def _create_splash_pixmap(width: int = 560, height: int = 320):
    """Build the splash pixmap: image fills the canvas, with a horizontal
    gradient overlay that leaves the left half clear and fades the right
    half toward dark, and PolyCAD branding text rendered on the dark side."""
    from PySide6.QtCore import Qt, QRectF
    from PySide6.QtGui import (
        QPixmap, QPainter, QLinearGradient, QColor, QFont, QPen, QBrush,
    )

    icons_dir = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "icons"
    )
    image_path = os.path.join(icons_dir, "13209590_black-weiss-eye.jpg")

    canvas = QPixmap(width, height)
    canvas.fill(QColor("#0d0d18"))   # solid fallback if image is missing

    p = QPainter(canvas)
    p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)

    # 1) Image, scaled to cover and center-cropped
    src = QPixmap(image_path)
    if not src.isNull():
        scaled = src.scaled(
            width, height,
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation,
        )
        sx = max(0, (scaled.width() - width) // 2)
        sy = max(0, (scaled.height() - height) // 2)
        p.drawPixmap(0, 0, scaled, sx, sy, width, height)

    # 2) Horizontal darkening gradient — left half stays clear,
    #    right half progressively darkens toward the edge
    grad = QLinearGradient(0, 0, width, 0)
    dark = QColor(13, 13, 24)
    def _stop(alpha):
        c = QColor(dark); c.setAlpha(alpha); return c
    grad.setColorAt(0.00, _stop(0))
    grad.setColorAt(0.40, _stop(0))       # clear plateau on the left
    grad.setColorAt(0.55, _stop(50))      # darkening starts past midpoint
    grad.setColorAt(0.75, _stop(165))
    grad.setColorAt(1.00, _stop(235))     # near-opaque on the right edge
    p.fillRect(0, 0, width, height, QBrush(grad))

    # 3) Branding text on the dark side
    text_x = int(width * 0.58)
    text_w = width - text_x - 24

    # Title
    p.setFont(QFont("Segoe UI", 30, QFont.Weight.Bold))
    p.setPen(QColor("#cdd6f4"))
    p.drawText(
        QRectF(text_x, 64, text_w, 52),
        int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
        "PolyCAD",
    )

    # Subtitle (blue accent)
    p.setFont(QFont("Segoe UI", 10, QFont.Weight.DemiBold))
    p.setPen(QColor("#89b4fa"))
    p.drawText(
        QRectF(text_x, 118, text_w, 18),
        int(Qt.AlignmentFlag.AlignLeft),
        "3D CAD Application",
    )

    # Version label
    p.setFont(QFont("Segoe UI", 8))
    p.setPen(QColor("#6c7086"))
    p.drawText(
        QRectF(text_x, 140, text_w, 16),
        int(Qt.AlignmentFlag.AlignLeft),
        "v0.1  ·  pre-alpha",
    )

    # Thin separator above the dynamic status line
    p.setPen(QPen(QColor("#313244"), 1))
    p.drawLine(text_x, height - 44, width - 24, height - 44)

    p.end()
    return canvas

def _get_stylesheet() -> str:
    import shutil, tempfile
    _icons_dir = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "icons"
    )

    # Qt stylesheet url() fails on non-ASCII paths (e.g. "Masaüstü") on
    # Windows. Copy icons into an ASCII-safe temp dir and reference those.
    _ascii_dir = os.path.join(tempfile.gettempdir(), "polycad_icons")
    os.makedirs(_ascii_dir, exist_ok=True)
    for _name in ("arrow_up.png", "arrow_down.png"):
        _src = os.path.join(_icons_dir, _name)
        _dst = os.path.join(_ascii_dir, _name)
        if os.path.exists(_src):
            shutil.copyfile(_src, _dst)

    _arrow_up = os.path.join(_ascii_dir, "arrow_up.png").replace("\\", "/")
    _arrow_down = os.path.join(_ascii_dir, "arrow_down.png").replace("\\", "/")
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
        image: url("%%ARROW_UP%%");
        width: 9px;
        height: 7px;
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
        image: url("%%ARROW_DOWN%%");
        width: 9px;
        height: 7px;
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
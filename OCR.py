"""
OCR Text Snipper — Enhanced
────────────────────────────
A screen-region OCR tool that lives in the system tray.

Usage:
  • Press Ctrl+Shift+S (or double-click the tray icon) to enter snip mode.
  • Draw a rectangle around any text on screen.
  • The extracted text appears in a floating popup and is copied to clipboard.
  • Access recent snips from the tray menu.

Requirements:
  pip install PyQt5 mss Pillow pytesseract pyperclip
  + Tesseract OCR: https://github.com/UB-Mannheim/tesseract/wiki
"""

import sys
import os
import json
import datetime
import shutil
from pathlib import Path

from PyQt5 import QtWidgets, QtGui, QtCore
from PyQt5.QtWidgets import (
    QSystemTrayIcon, QMenu, QAction, QApplication,
    QDialog, QVBoxLayout, QHBoxLayout, QTextEdit,
    QPushButton, QLabel, QWidget, QFrame,
)
from PyQt5.QtCore import Qt, QRect, QTimer, pyqtSignal
from PyQt5.QtGui import (
    QPainter, QPen, QColor, QFont, QBrush,
    QPixmap, QIcon, QCursor,
)

import mss
from PIL import Image
import pytesseract
import pyperclip

# ─── Tesseract auto-detection ───────────────────────────────────────────────

def find_tesseract() -> str | None:
    """Locate the Tesseract binary without a hardcoded path."""
    candidates = [
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
        rf"C:\Users\{os.environ.get('USERNAME','')}\AppData\Local\Programs\Tesseract-OCR\tesseract.exe",
    ]
    for path in candidates:
        if os.path.isfile(path):
            return path
    return shutil.which("tesseract")  # Linux / macOS / PATH-based installs


tess_path = find_tesseract()
if tess_path:
    pytesseract.pytesseract.tesseract_cmd = tess_path
else:
    print(
        "⚠  Tesseract not found. Install it from:\n"
        "   https://github.com/UB-Mannheim/tesseract/wiki\n"
        "   (Windows) or  brew install tesseract  (macOS)"
    )

# ─── Palette (Catppuccin Mocha) ──────────────────────────────────────────────

C = {
    "base":    "#1e1e2e",
    "mantle":  "#181825",
    "surface": "#313244",
    "overlay": "#45475a",
    "text":    "#cdd6f4",
    "subtext": "#a6adc8",
    "muted":   "#585b70",
    "blue":    "#89b4fa",
    "lavender":"#b4befe",
    "red":     "#f38ba8",
    "green":   "#a6e3a1",
}

HISTORY_PATH = Path.home() / ".ocr_snipper_history.json"
MAX_HISTORY  = 20
HOTKEY_ID    = 0xBEEF


# ─── History ─────────────────────────────────────────────────────────────────

class HistoryManager:
    def __init__(self):
        self.entries: list[dict] = []
        self._load()

    def _load(self):
        try:
            if HISTORY_PATH.exists():
                self.entries = json.loads(HISTORY_PATH.read_text(encoding="utf-8"))
        except Exception:
            self.entries = []

    def _save(self):
        try:
            HISTORY_PATH.write_text(
                json.dumps(self.entries[-MAX_HISTORY:], ensure_ascii=False),
                encoding="utf-8",
            )
        except Exception:
            pass

    def add(self, text: str):
        self.entries.append({
            "text": text,
            "ts":   datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
        })
        if len(self.entries) > MAX_HISTORY:
            self.entries = self.entries[-MAX_HISTORY:]
        self._save()

    def recent(self, n: int = 5) -> list[dict]:
        return list(reversed(self.entries[-n:]))


# ─── Result popup ─────────────────────────────────────────────────────────────

class ResultWindow(QWidget):
    """Frameless floating card showing the OCR result."""

    def __init__(self, text: str):
        super().__init__(None, Qt.Tool | Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self._drag_pos = None

        self._build_ui(text)
        self._position_near_cursor()

        # Auto-dismiss after 10 s if not interacted with
        self._timer = QTimer(singleShot=True)
        self._timer.timeout.connect(self.close)
        self._timer.start(10_000)

    # ── Layout ──────────────────────────────────────────────────────────────

    def _build_ui(self, text: str):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 8, 8, 8)   # shadow room

        card = QFrame()
        card.setStyleSheet(f"""
            QFrame {{
                background: {C['base']};
                border: 1px solid {C['overlay']};
                border-radius: 14px;
            }}
        """)
        card_lay = QVBoxLayout(card)
        card_lay.setContentsMargins(16, 14, 16, 14)
        card_lay.setSpacing(10)

        # ── Header row ──────────────────────────────────────────────────────
        header_row = QHBoxLayout()

        icon_lbl = QLabel("✂")
        icon_lbl.setStyleSheet(f"color:{C['blue']}; font-size:16px; background:transparent; border:none;")
        title_lbl = QLabel("OCR Result")
        title_lbl.setStyleSheet(f"color:{C['text']}; font-weight:600; font-size:13px; background:transparent; border:none;")

        close_btn = QPushButton("✕")
        close_btn.setFixedSize(22, 22)
        close_btn.setStyleSheet(f"""
            QPushButton {{
                color:{C['muted']}; background:transparent; border:none; font-size:12px;
            }}
            QPushButton:hover {{ color:{C['red']}; }}
        """)
        close_btn.clicked.connect(self.close)

        header_row.addWidget(icon_lbl)
        header_row.addWidget(title_lbl)
        header_row.addStretch()
        header_row.addWidget(close_btn)
        card_lay.addLayout(header_row)

        # Divider
        div = QFrame(); div.setFrameShape(QFrame.HLine)
        div.setStyleSheet(f"background:{C['surface']}; border:none; max-height:1px;")
        card_lay.addWidget(div)

        # ── Text area ────────────────────────────────────────────────────────
        self.edit = QTextEdit()
        self.edit.setPlainText(text.strip())
        self.edit.setMinimumWidth(300)
        self.edit.setMaximumWidth(460)
        self.edit.setMinimumHeight(70)
        self.edit.setMaximumHeight(180)
        self.edit.setStyleSheet(f"""
            QTextEdit {{
                background:{C['mantle']}; color:{C['text']};
                border:1px solid {C['surface']}; border-radius:8px;
                padding:8px;
                font-family:'Consolas','Menlo','Courier New',monospace;
                font-size:12px; line-height:1.5;
            }}
        """)
        self.edit.mousePressEvent = lambda e: (self._timer.stop(), QTextEdit.mousePressEvent(self.edit, e))
        card_lay.addWidget(self.edit)

        # ── Stats ────────────────────────────────────────────────────────────
        stripped = text.strip()
        words  = len(stripped.split()) if stripped else 0
        chars  = len(stripped)
        stats = QLabel(f"{words} word{'s' if words!=1 else ''} · {chars} character{'s' if chars!=1 else ''}")
        stats.setStyleSheet(f"color:{C['muted']}; font-size:11px; background:transparent; border:none;")
        card_lay.addWidget(stats)

        # ── Buttons ──────────────────────────────────────────────────────────
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        dismiss_btn = QPushButton("Dismiss")
        dismiss_btn.setStyleSheet(f"""
            QPushButton {{
                color:{C['subtext']}; background:transparent;
                border:1px solid {C['surface']}; border-radius:7px;
                padding:5px 14px; font-size:12px;
            }}
            QPushButton:hover {{ color:{C['text']}; border-color:{C['overlay']}; }}
        """)
        dismiss_btn.clicked.connect(self.close)

        copy_btn = QPushButton("Copy Text")
        copy_btn.setStyleSheet(f"""
            QPushButton {{
                color:{C['base']}; background:{C['blue']};
                border:none; border-radius:7px;
                padding:5px 16px; font-size:12px; font-weight:600;
            }}
            QPushButton:hover {{ background:{C['lavender']}; }}
        """)
        copy_btn.clicked.connect(self._copy_and_close)

        btn_row.addStretch()
        btn_row.addWidget(dismiss_btn)
        btn_row.addWidget(copy_btn)
        card_lay.addLayout(btn_row)

        outer.addWidget(card)

    # ── Helpers ─────────────────────────────────────────────────────────────

    def _copy_and_close(self):
        pyperclip.copy(self.edit.toPlainText())
        self.close()

    def _position_near_cursor(self):
        self.adjustSize()
        pos    = QCursor.pos()
        screen = QApplication.screenAt(pos)
        if not screen:
            screen = QApplication.primaryScreen()
        geo = screen.availableGeometry()
        x = min(pos.x() + 24, geo.right()  - self.width()  - 12)
        y = min(pos.y() + 24, geo.bottom() - self.height() - 12)
        self.move(max(geo.left(), x), max(geo.top(), y))

    # ── Dragging ─────────────────────────────────────────────────────────────

    def mousePressEvent(self, e):
        self._timer.stop()
        if e.button() == Qt.LeftButton:
            self._drag_pos = e.globalPos() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, e):
        if self._drag_pos and e.buttons() & Qt.LeftButton:
            self.move(e.globalPos() - self._drag_pos)

    def mouseReleaseEvent(self, e):
        self._drag_pos = None


# ─── Snip overlay ─────────────────────────────────────────────────────────────

class SnipOverlay(QWidget):
    """Full-screen semi-transparent overlay; selected area is 'punched out'."""

    ocr_complete = pyqtSignal(str)   # emitted with extracted text (or "")
    cancelled    = pyqtSignal()

    def __init__(self, screenshot: Image.Image, dpr: float):
        super().__init__(
            None,
            Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.SplashScreen,
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_DeleteOnClose)

        self._screenshot = screenshot
        self._dpr        = dpr          # device-pixel ratio for HiDPI
        self._start      = None
        self._end        = None

        # Span all monitors
        virt = QApplication.primaryScreen().virtualGeometry()
        self.setGeometry(virt)
        self.setCursor(Qt.CrossCursor)
        self.setMouseTracking(True)

    # ── Input ────────────────────────────────────────────────────────────────

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_Escape:
            self.cancelled.emit()
            self.close()

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._start = e.pos()
            self._end   = e.pos()
            self.update()

    def mouseMoveEvent(self, e):
        if self._start:
            self._end = e.pos()
            self.update()

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.LeftButton and self._start:
            self._end = e.pos()
            self._run_ocr()
            self.close()

    # ── Painting ─────────────────────────────────────────────────────────────

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)

        # Dark vignette over everything
        p.fillRect(self.rect(), QColor(0, 0, 0, 140))

        if self._start and self._end:
            sel = QRect(self._start, self._end).normalized()

            # Punch out the selection (CompositionMode_Clear reveals transparency)
            p.setCompositionMode(QPainter.CompositionMode_Clear)
            p.fillRect(sel, QColor(0, 0, 0, 255))
            p.setCompositionMode(QPainter.CompositionMode_SourceOver)

            # Crisp blue border around selection
            p.setPen(QPen(QColor(C["blue"]), 2, Qt.SolidLine, Qt.SquareCap, Qt.MiterJoin))
            p.drawRect(sel)

            # Corner handles
            corner_size = 6
            p.setBrush(QBrush(QColor(C["blue"])))
            p.setPen(Qt.NoPen)
            for cx, cy in [
                (sel.left(), sel.top()), (sel.right(), sel.top()),
                (sel.left(), sel.bottom()), (sel.right(), sel.bottom()),
            ]:
                p.drawRect(cx - corner_size//2, cy - corner_size//2, corner_size, corner_size)

            # Dimension badge
            w, h = sel.width(), sel.height()
            badge = f" {w} × {h} "
            p.setFont(QFont("Arial", 10, QFont.Bold))
            fm    = p.fontMetrics()
            bw    = fm.horizontalAdvance(badge) + 4
            bh    = fm.height() + 4
            bx    = sel.right() - bw - 4
            by    = sel.top() - bh - 4 if sel.top() > bh + 8 else sel.bottom() + 4

            p.setBrush(QBrush(QColor(C["blue"])))
            p.setPen(Qt.NoPen)
            p.drawRoundedRect(bx, by, bw, bh, 4, 4)
            p.setPen(QColor(C["base"]))
            p.drawText(bx, by, bw, bh, Qt.AlignCenter, badge)

        # Instruction banner
        banner_h = 36
        p.fillRect(0, 0, self.width(), banner_h, QColor(0, 0, 0, 170))
        p.setPen(QColor(C["subtext"]))
        p.setFont(QFont("Arial", 11))
        p.drawText(16, banner_h - 10, "Draw a region to extract text   ·   Esc to cancel")

    # ── OCR ──────────────────────────────────────────────────────────────────

    def _run_ocr(self):
        if not (self._start and self._end):
            self.ocr_complete.emit("")
            return

        sel = QRect(self._start, self._end).normalized()
        if sel.width() < 4 or sel.height() < 4:
            self.ocr_complete.emit("")
            return

        # Map widget coords → physical pixels (HiDPI)
        dpr = self._dpr
        x1, y1 = int(sel.left() * dpr), int(sel.top() * dpr)
        x2, y2 = int(sel.right() * dpr), int(sel.bottom() * dpr)

        crop = self._screenshot.crop((x1, y1, x2, y2))

        # Upscale tiny regions so Tesseract has enough pixels
        cw, ch = crop.size
        if max(cw, ch) < 300:
            scale = max(2, 300 // max(cw, ch, 1))
            crop  = crop.resize((cw * scale, ch * scale), Image.LANCZOS)

        # PSM 6 = "assume a single uniform block of text" — works well for screenshots
        text = pytesseract.image_to_string(crop, config="--psm 6").strip()
        self.ocr_complete.emit(text)


# ─── System-tray application ──────────────────────────────────────────────────

class OCRSnipperApp(QApplication):

    def __init__(self, argv):
        super().__init__(argv)
        self.setQuitOnLastWindowClosed(False)
        self.setApplicationName("OCR Text Snipper")

        self._history      = HistoryManager()
        self._overlay      = None
        self._result_win   = None
        self._hotkey_timer = None

        self._build_tray()
        self._register_hotkey()

        # Startup toast
        QTimer.singleShot(600, self._startup_toast)

    # ── Tray ─────────────────────────────────────────────────────────────────

    def _build_tray(self):
        self._tray = QSystemTrayIcon(self._make_icon(), self)
        self._tray.setToolTip("OCR Text Snipper — Ctrl+Shift+S to snip")

        menu = QMenu()
        menu.setStyleSheet(f"""
            QMenu {{
                background:{C['base']}; color:{C['text']};
                border:1px solid {C['overlay']}; border-radius:8px;
                padding:4px;
            }}
            QMenu::item {{ padding:6px 20px 6px 12px; border-radius:6px; }}
            QMenu::item:selected {{ background:{C['surface']}; }}
            QMenu::separator {{ height:1px; background:{C['surface']}; margin:4px 8px; }}
        """)

        snip_act = QAction("✂  Snip Region  (Ctrl+Shift+S)", self)
        snip_act.triggered.connect(self.start_snip)
        menu.addAction(snip_act)

        menu.addSeparator()

        self._hist_menu = QMenu("📋  Recent Snips", menu)
        self._hist_menu.setStyleSheet(menu.styleSheet())
        menu.addMenu(self._hist_menu)
        self._refresh_history_menu()

        menu.addSeparator()

        quit_act = QAction("Quit", self)
        quit_act.triggered.connect(self.quit)
        menu.addAction(quit_act)

        self._tray.setContextMenu(menu)
        self._tray.activated.connect(self._on_tray_activated)
        self._tray.show()

    def _make_icon(self) -> QIcon:
        """Draw a simple scissors icon programmatically."""
        px = QPixmap(64, 64)
        px.fill(Qt.transparent)
        p  = QPainter(px)
        p.setRenderHint(QPainter.Antialiasing)
        p.setBrush(QBrush(QColor(C["blue"])))
        p.setPen(Qt.NoPen)
        p.drawRoundedRect(4, 4, 56, 56, 14, 14)
        p.setPen(QColor(C["base"]))
        p.setFont(QFont("Segoe UI Emoji", 26))
        p.drawText(px.rect(), Qt.AlignCenter, "✂")
        p.end()
        return QIcon(px)

    def _refresh_history_menu(self):
        self._hist_menu.clear()
        recent = self._history.recent(8)
        if not recent:
            empty = QAction("No recent snips", self)
            empty.setEnabled(False)
            self._hist_menu.addAction(empty)
            return
        for entry in recent:
            label = entry["text"][:60].replace("\n", " ")
            if len(entry["text"]) > 60:
                label += "…"
            act = QAction(f"[{entry['ts']}]  {label}", self)
            act.triggered.connect(lambda _=False, t=entry["text"]: pyperclip.copy(t))
            self._hist_menu.addAction(act)

    def _on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.DoubleClick:
            self.start_snip()

    # ── Global hotkey (Windows) ───────────────────────────────────────────────

    def _register_hotkey(self):
        try:
            import ctypes
            from ctypes import wintypes
            MOD_CTRL  = 0x0002
            MOD_SHIFT = 0x0004
            VK_S      = 0x53
            if ctypes.windll.user32.RegisterHotKey(None, HOTKEY_ID, MOD_CTRL | MOD_SHIFT, VK_S):
                self._hotkey_timer = QTimer(interval=100)
                self._hotkey_timer.timeout.connect(self._poll_hotkey)
                self._hotkey_timer.start()
        except Exception:
            pass   # Non-Windows; hotkey unavailable (use tray double-click instead)
 
    def _poll_hotkey(self):
        try:
            import ctypes
            from ctypes import wintypes
            msg = wintypes.MSG()
            if ctypes.windll.user32.PeekMessageW(ctypes.byref(msg), None, 0x0312, 0x0312, 1):
                if msg.message == 0x0312 and msg.wParam == HOTKEY_ID:
                    self.start_snip()
        except Exception:
            pass

    # ── Snip workflow ─────────────────────────────────────────────────────────

    def start_snip(self):
        if self._overlay:
            return   # Already active

        # Capture the screen now (before the overlay appears)
        dpr = QApplication.primaryScreen().devicePixelRatio()
        with mss.mss() as sct:
            mon = sct.monitors[0]   # 0 = all monitors combined
            raw = sct.grab(mon)
            screenshot = Image.frombytes("RGB", raw.size, raw.rgb)

        self._overlay = SnipOverlay(screenshot, dpr)
        self._overlay.ocr_complete.connect(self._on_ocr_done)
        self._overlay.cancelled.connect(lambda: setattr(self, "_overlay", None))
        self._overlay.destroyed.connect(lambda: setattr(self, "_overlay", None))
        self._overlay.showFullScreen()
        self._overlay.activateWindow()
        self._overlay.raise_()

    def _on_ocr_done(self, text: str):
        self._overlay = None

        if not text:
            self._tray.showMessage(
                "No text found",
                "Couldn't extract readable text from that region.",
                QSystemTrayIcon.Warning,
                2_500,
            )
            return

        pyperclip.copy(text)
        self._history.add(text)
        self._refresh_history_menu()

        # Show result card
        if self._result_win:
            self._result_win.close()
        self._result_win = ResultWindow(text)
        self._result_win.show()

        # Tray notification (brief)
        preview = text[:80] + ("…" if len(text) > 80 else "")
        self._tray.showMessage("Text copied!", preview, QSystemTrayIcon.Information, 2_000)

    def _startup_toast(self):
        self._tray.showMessage(
            "OCR Text Snipper",
            "Running in tray — press Ctrl+Shift+S or double-click to snip.",
            QSystemTrayIcon.Information,
            3_500,
        )


# ─── Entry point ──────────────────────────────────────────────────────────────

def main():
    app = OCRSnipperApp(sys.argv)
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()

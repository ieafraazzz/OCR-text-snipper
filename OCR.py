# save as screen_ocr_selector.py
import sys
import io
from PyQt5 import QtWidgets, QtGui, QtCore
import mss
import mss.tools
from PIL import Image
import pytesseract
import pyperclip

pytesseract.pytesseract.tesseract_cmd = r'C:\Users\ieafr\AppData\Local\Programs\Tesseract-OCR\tesseract.exe'


class SnipWidget(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowState(QtCore.Qt.WindowFullScreen)
        self.setWindowOpacity(0.3)
        # Optional: Changes cursor to a crosshair
        self.setCursor(QtCore.Qt.CrossCursor)
        self.start = None
        self.end = None

    def mousePressEvent(self, e):
        self.start = e.pos()
        self.end = self.start

    def mouseMoveEvent(self, e):
        self.end = e.pos()
        self.update()  # Triggers paintEvent to redraw the rectangle

    def mouseReleaseEvent(self, e):
        self.end = e.pos()
        self.capture_and_ocr()
        QtWidgets.qApp.quit()

    def paintEvent(self, e):
        if self.start and self.end:
            qp = QtGui.QPainter(self)
            rect = QtCore.QRect(self.start, self.end)
            qp.setPen(QtGui.QPen(QtCore.Qt.red, 2))
            qp.drawRect(rect)

    def capture_and_ocr(self):
        x1, y1 = min(self.start.x(), self.end.x()), min(
            self.start.y(), self.end.y())
        x2, y2 = max(self.start.x(), self.end.x()), max(
            self.start.y(), self.end.y())

        # Prevent crash if the user just clicked without dragging
        if x2 - x1 <= 0 or y2 - y1 <= 0:
            print("Selection area too small.")
            return

        with mss.mss() as sct:
            monitor = {"left": x1, "top": y1, "width": x2-x1, "height": y2-y1}
            sct_img = sct.grab(monitor)
            img = Image.frombytes("RGB", sct_img.size, sct_img.rgb)
            text = pytesseract.image_to_string(img)
            pyperclip.copy(text)
            print("Copied text:", text)


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    w = SnipWidget()
    w.show()
    sys.exit(app.exec_())

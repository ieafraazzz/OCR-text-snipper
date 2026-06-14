# ✂ OCR Text Snipper

A lightweight screen-region OCR tool that lives in your system tray. Draw a box around any text on your screen — it's instantly extracted and copied to your clipboard.

![Python](https://img.shields.io/badge/Python-3.10+-blue?logo=python&logoColor=white)
![PyQt5](https://img.shields.io/badge/UI-PyQt5-41cd52?logo=qt)
![Tesseract](https://img.shields.io/badge/OCR-Tesseract-red)
![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey)

---

## Features

- **System tray app** — runs quietly in the background, always one shortcut away
- **Global hotkey** — `Ctrl+Shift+S` triggers snip mode from anywhere (Windows)
- **Punch-out overlay** — selected region stays bright while the rest dims, just like the Windows Snipping Tool
- **Result popup** — floating card shows the extracted text; edit it before copying, or dismiss it
- **Auto-dismiss** — the popup closes itself after 10 seconds if left alone
- **Snip history** — last 20 snips are stored locally and accessible from the tray menu
- **HiDPI support** — device-pixel-ratio aware for crisp captures on Retina / 4K displays
- **Auto-upscaling** — small regions are automatically upscaled before OCR for better accuracy
- **Auto-detects Tesseract** — no hardcoded paths; searches common install locations automatically

---

## Installation

### 1. Install Tesseract OCR

| Platform | Command |
|---|---|
| **Windows** | Download installer from [UB Mannheim](https://github.com/UB-Mannheim/tesseract/wiki) |
| **macOS** | `brew install tesseract` |
| **Linux** | `sudo apt install tesseract-ocr` |

### 2. Install Python dependencies

```bash
pip install PyQt5 mss Pillow pytesseract pyperclip
```

### 3. Run

```bash
python OCR.py
```

The scissors icon will appear in your system tray.

---

## Usage

| Action | Result |
|---|---|
| `Ctrl+Shift+S` | Enter snip mode |
| Double-click tray icon | Enter snip mode |
| Draw rectangle on screen | Extract & copy text |
| `Esc` | Cancel snip |
| Click "Copy Text" in popup | Copy (possibly edited) text |
| Drag popup | Move the result card around |
| Tray → Recent Snips | Re-copy a previous result |

---

## How it works

```
Hotkey / tray click
        │
        ▼
 Capture full screen (mss)
        │
        ▼
 Show punch-out overlay (PyQt5)
        │
   User draws region
        │
        ▼
 Crop → upscale if tiny → Tesseract OCR (pytesseract)
        │
        ▼
 Copy to clipboard (pyperclip) + save to history
        │
        ▼
 Show floating result card (editable)
```

---

## Project structure

```
OCR-text-snipper/
├── OCR.py        # Main script — everything in one file
└── README.md
```

---

## Tips for better results

- **Too much noise?** Zoom in before snipping, or snip a tighter region around just the text.
- **Non-Latin languages?** Pass a language code: change `--psm 6` to `--psm 6 -l jpn` (etc.) and install the relevant Tesseract language pack.
- **Very small text?** The auto-upscaler kicks in for regions under 300px, but scaling your display before snipping also helps.

---

## Requirements

- Python 3.10+
- PyQt5 ≥ 5.15
- Pillow ≥ 9.0
- pytesseract ≥ 0.3
- mss ≥ 9.0
- pyperclip ≥ 1.8
- Tesseract OCR binary (any recent version)

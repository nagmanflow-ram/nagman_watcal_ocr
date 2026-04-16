#!/usr/bin/env python
# coding: utf-8

# 

# In[3]:


import subprocess, sys

packages = ["opencv-python", "numpy", "Pillow", "easyocr", "pytesseract"]
for pkg in packages:

print("✅ All packages installed.")


# In[7]:


# ============================================================
#  CELL 1 – Install dependencies  (run once)
# ============================================================

import subprocess, sys

packages = ["opencv-python", "numpy", "Pillow", "ddddocr"]
for pkg in packages:
    result = subprocess.run(
        [sys.executable, "-m", "pip", "install", pkg, "-q"],
        capture_output=True, text=True
    )
    print(f"{'✅' if result.returncode == 0 else '❌'} {pkg}")

print("\n✅ Done. Run Cell 2 next.")


# ============================================================
#  CELL 2 – Full Flow Meter Reader
# ============================================================

import re
import io
import os
import cv2
import numpy as np
from pathlib import Path
from dataclasses import dataclass

# ── Data class ────────────────────────────────────────────────
@dataclass
class MeterReading:
    raw_text:     str
    integer_part: str
    decimal_part: str
    full_value:   float
    confidence:   float


# ── Pre-processing ────────────────────────────────────────────
def preprocess(image_path: str):
    img = cv2.imread(image_path)
    if img is None:
        from PIL import Image
        pil_img = Image.open(image_path).convert("RGB")
        img = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    h, w = gray.shape
    if w < 600:
        scale = 600 / w
        gray = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
        img  = cv2.resize(img,  None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)

    denoised  = cv2.fastNlMeansDenoising(gray, h=10)
    thresh    = cv2.adaptiveThreshold(denoised, 255,
                    cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2)
    kernel    = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
    processed = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)

    return img, gray, processed


# ── Auto-crop the dial strip ──────────────────────────────────
def isolate_dial_region(img: np.ndarray) -> np.ndarray:
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if len(img.shape) == 3 else img
    edges = cv2.Canny(gray, 50, 150)
    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    best, best_area = None, 0
    ih, iw = gray.shape[:2]

    for cnt in contours:
        x, y, w, h = cv2.boundingRect(cnt)
        aspect = w / max(h, 1)
        area   = w * h
        if aspect > 2.5 and area > best_area and w > iw * 0.4:
            best_area = area
            best = (x, y, w, h)

    if best:
        x, y, w, h = best
        pad = 10
        return img[max(0,y-pad):min(ih,y+h+pad), max(0,x-pad):min(iw,x+w+pad)]
    return img


# ── Detect red digit columns (decimal marker) ─────────────────
def find_red_digit_columns(img_bgr: np.ndarray) -> list:
    hsv   = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)
    mask1 = cv2.inRange(hsv, np.array([0,  100, 80]), np.array([10,  255, 255]))
    mask2 = cv2.inRange(hsv, np.array([160, 100, 80]), np.array([180, 255, 255]))
    red   = cv2.bitwise_or(mask1, mask2)

    col_sum   = np.sum(red, axis=0)
    threshold = red.shape[0] * 0.08 * 255
    red_cols  = np.where(col_sum > threshold)[0]

    if len(red_cols) == 0:
        return []

    ranges, start, prev = [], int(red_cols[0]), int(red_cols[0])
    for c in red_cols[1:]:
        if c - prev > 5:
            ranges.append((start, prev))
            start = int(c)
        prev = int(c)
    ranges.append((start, prev))
    return ranges


# ── count how many digit cells are red ────────────────────────
def count_red_digit_cells(img_bgr: np.ndarray, n_digits: int) -> int:
    """
    Divide the dial image into n_digits equal vertical cells.
    Count how many cells on the RIGHT side are predominantly red.
    This gives a reliable decimal_digits count directly from the image.
    """
    hsv   = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)
    mask1 = cv2.inRange(hsv, np.array([0,  80, 80]), np.array([10,  255, 255]))
    mask2 = cv2.inRange(hsv, np.array([160, 80, 80]), np.array([180, 255, 255]))
    red   = cv2.bitwise_or(mask1, mask2)

    h, w  = red.shape
    cell_w = w / n_digits
    red_count = 0

    # check cells from right to left; stop when cell is no longer red
    for i in range(n_digits - 1, -1, -1):
        x1 = int(i * cell_w)
        x2 = int((i + 1) * cell_w)
        cell = red[:, x1:x2]
        red_ratio = np.sum(cell > 0) / max(cell.size, 1)
        if red_ratio > 0.05:   # >5 % red pixels → this cell is a red digit
            red_count += 1
        else:
            break              # stop as soon as a non-red cell is found

    return max(red_count, 0)


# ── ddddocr engine (replaces EasyOCR + Tesseract) ─────────────
def read_with_ddddocr(image_bgr: np.ndarray) -> tuple:
    import ddddocr
    from PIL import Image

    ocr = ddddocr.DdddOcr(show_ad=False)

    rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
    pil = Image.fromarray(rgb)

    buf = io.BytesIO()
    pil.save(buf, format="PNG")
    result = ocr.classification(buf.getvalue())

    digits = re.sub(r'\D', '', result)
    return digits, 0.95


# ── Master reader ─────────────────────────────────────────────
def read_meter(image_path: str, decimal_digits: int = 1, debug: bool = False) -> MeterReading:
    img_bgr, gray, processed = preprocess(image_path)
    dial = isolate_dial_region(img_bgr)

    if debug:
        from IPython.display import display
        import PIL.Image
        display(PIL.Image.fromarray(cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)))
        display(PIL.Image.fromarray(cv2.cvtColor(dial,    cv2.COLOR_BGR2RGB)))

    red_ranges = find_red_digit_columns(dial)

    # ── Try ddddocr on cropped dial ──────────────────────────
    raw_text, confidence, engine = "", 0.0, "none"
    try:
        raw_text, confidence = read_with_ddddocr(dial)
        engine = "ddddocr"
    except Exception as e:
        print(f"[WARN] ddddocr on dial failed: {e}")

    # ── Retry on thresholded image if empty ─────────────────
    if not re.sub(r'\D', '', raw_text):
        try:
            dial_gray3 = cv2.cvtColor(processed, cv2.COLOR_GRAY2BGR)
            raw_text, confidence = read_with_ddddocr(dial_gray3)
            engine = "ddddocr+thresh"
        except Exception as e:
            print(f"[WARN] ddddocr on thresh failed: {e}")

    digits = re.sub(r'\D', '', raw_text)
    print(f"[INFO] Engine: {engine} | Raw: '{raw_text}' | Digits: '{digits}'")

    # ── Auto-detect decimal digit count from red cells ───────
    # Overrides the passed-in decimal_digits with what's actually
    # visible as red in the image — gives correct split every time.
    if digits:
        detected_dec = count_red_digit_cells(dial, len(digits))
        if detected_dec > 0:
            decimal_digits = detected_dec
            print(f"[INFO] Auto-detected {decimal_digits} red (decimal) digit(s)")

    # ── Split integer / decimal ──────────────────────────────
    split_idx    = len(digits) - decimal_digits
    split_idx    = max(0, min(split_idx, len(digits)))   # clamp to valid range

    integer_part = digits[:split_idx] if split_idx > 0          else digits
    decimal_part = digits[split_idx:] if split_idx < len(digits) else ""

    # ── Build final value preserving leading zeros ───────────
    # e.g. digits="000819", integer="00081", decimal="9"
    # → full_value string = "00081.9"  (printed as-is, not as float)
    full_value_str = f"{integer_part}.{decimal_part}" if decimal_part else integer_part

    try:
        full_value = float(full_value_str)
    except ValueError:
        full_value = 0.0

    print(f"[INFO] Split → integer='{integer_part}'  decimal='{decimal_part}'  value='{full_value_str}'")

    return MeterReading(raw_text, integer_part, decimal_part, full_value, confidence)


print("✅ All functions loaded. Run Cell 3 to read your meter.")


# ============================================================
#  CELL 3 – Run on your image
# ============================================================

IMAGE_PATH     = "/home/akill-sud/Documents/projects/nagman_callibration/cropped_dataset/test/id_0289_meter_1_3.png"
DECIMAL_DIGITS = 1    # fallback if red-cell auto-detection finds nothing

reading = read_meter(IMAGE_PATH, decimal_digits=DECIMAL_DIGITS, debug=True)

# Build display string that preserves leading zeros (e.g. "00081.9")
display_value = f"{reading.integer_part}.{reading.decimal_part}" \
                if reading.decimal_part else reading.integer_part

print("\n" + "═" * 45)
print(f"  📟 Meter Reading  :  {display_value}")
print(f"  🔢 Integer part   :  {reading.integer_part}")
print(f"  🔴 Decimal part   :  {reading.decimal_part}")
print(f"  📊 OCR Confidence :  {reading.confidence:.2%}")
print("═" * 45)


# ============================================================
#  CELL 4 – Batch process a folder of images
# ============================================================

def batch_read(folder: str, decimal_digits: int = 1) -> list:
    results = []
    exts = (".jpg", ".jpeg", ".png", ".bmp")
    for p in sorted(Path(folder).iterdir()):
        if p.suffix.lower() in exts:
            try:
                r = read_meter(str(p), decimal_digits=decimal_digits)
                display_val = f"{r.integer_part}.{r.decimal_part}" \
                              if r.decimal_part else r.integer_part
                row = {"file": p.name, "value": display_val,
                       "integer": r.integer_part, "decimal": r.decimal_part,
                       "confidence": round(r.confidence, 3)}
                print(f"  ✓ {p.name:40s}  →  {display_val}  (conf={r.confidence:.2f})")
            except Exception as e:
                row = {"file": p.name, "value": None, "error": str(e)}
                print(f"  ✗ {p.name:40s}  →  ERROR: {e}")
            results.append(row)
    return results


results = batch_read(
    "/home/akill-sud/Documents/projects/nagman_callibration/cropped_dataset/test",
    decimal_digits=1
)

# Save to CSV (requires pandas):
# import pandas as pd
# pd.DataFrame(results).to_csv("meter_readings.csv", index=False)
# print("Saved to meter_readings.csv")


# In[8]:


# ============================================================
#  CELL 1 – Install dependencies  (run once)
# ============================================================

import subprocess, sys

packages = ["opencv-python", "numpy", "Pillow", "ddddocr"]
for pkg in packages:
    result = subprocess.run(
        [sys.executable, "-m", "pip", "install", pkg, "-q"],
        capture_output=True, text=True
    )
    print(f"{'✅' if result.returncode == 0 else '❌'} {pkg}")

print("\n✅ Done. Run Cell 2 next.")


# ============================================================
#  CELL 2 – Full Flow Meter Reader
# ============================================================

import re
import io
import os
import cv2
import numpy as np
from pathlib import Path
from dataclasses import dataclass

# ── Data class ────────────────────────────────────────────────
@dataclass
class MeterReading:
    raw_text:     str
    integer_part: str
    decimal_part: str
    full_value:   float
    confidence:   float


# ── Pre-processing ────────────────────────────────────────────
def preprocess(image_path: str):
    img = cv2.imread(image_path)
    if img is None:
        from PIL import Image
        pil_img = Image.open(image_path).convert("RGB")
        img = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    h, w = gray.shape
    if w < 600:
        scale = 600 / w
        gray = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
        img  = cv2.resize(img,  None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)

    denoised  = cv2.fastNlMeansDenoising(gray, h=10)
    thresh    = cv2.adaptiveThreshold(denoised, 255,
                    cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2)
    kernel    = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
    processed = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)

    return img, gray, processed


# ── Auto-crop the dial strip ──────────────────────────────────
def isolate_dial_region(img: np.ndarray) -> np.ndarray:
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if len(img.shape) == 3 else img
    edges = cv2.Canny(gray, 50, 150)
    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    best, best_area = None, 0
    ih, iw = gray.shape[:2]

    for cnt in contours:
        x, y, w, h = cv2.boundingRect(cnt)
        aspect = w / max(h, 1)
        area   = w * h
        if aspect > 2.5 and area > best_area and w > iw * 0.4:
            best_area = area
            best = (x, y, w, h)

    if best:
        x, y, w, h = best
        pad = 10
        return img[max(0,y-pad):min(ih,y+h+pad), max(0,x-pad):min(iw,x+w+pad)]
    return img


# ── Detect red digit columns (decimal marker) ─────────────────
def find_red_digit_columns(img_bgr: np.ndarray) -> list:
    hsv   = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)
    mask1 = cv2.inRange(hsv, np.array([0,  100, 80]), np.array([10,  255, 255]))
    mask2 = cv2.inRange(hsv, np.array([160, 100, 80]), np.array([180, 255, 255]))
    red   = cv2.bitwise_or(mask1, mask2)

    col_sum   = np.sum(red, axis=0)
    threshold = red.shape[0] * 0.08 * 255
    red_cols  = np.where(col_sum > threshold)[0]

    if len(red_cols) == 0:
        return []

    ranges, start, prev = [], int(red_cols[0]), int(red_cols[0])
    for c in red_cols[1:]:
        if c - prev > 5:
            ranges.append((start, prev))
            start = int(c)
        prev = int(c)
    ranges.append((start, prev))
    return ranges


# ── count how many digit cells are red ────────────────────────
def count_red_digit_cells(img_bgr: np.ndarray, n_digits: int) -> int:
    """
    Divide the dial image into n_digits equal vertical cells.
    Count how many cells on the RIGHT side are predominantly red.
    This gives a reliable decimal_digits count directly from the image.
    """
    hsv   = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)
    mask1 = cv2.inRange(hsv, np.array([0,  80, 80]), np.array([10,  255, 255]))
    mask2 = cv2.inRange(hsv, np.array([160, 80, 80]), np.array([180, 255, 255]))
    red   = cv2.bitwise_or(mask1, mask2)

    h, w  = red.shape
    cell_w = w / n_digits
    red_count = 0

    # check cells from right to left; stop when cell is no longer red
    for i in range(n_digits - 1, -1, -1):
        x1 = int(i * cell_w)
        x2 = int((i + 1) * cell_w)
        cell = red[:, x1:x2]
        red_ratio = np.sum(cell > 0) / max(cell.size, 1)
        if red_ratio > 0.05:   # >5 % red pixels → this cell is a red digit
            red_count += 1
        else:
            break              # stop as soon as a non-red cell is found

    return max(red_count, 0)


# ── ddddocr engine (replaces EasyOCR + Tesseract) ─────────────
def read_with_ddddocr(image_bgr: np.ndarray) -> tuple:
    import ddddocr
    from PIL import Image

    ocr = ddddocr.DdddOcr(show_ad=False)

    rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
    pil = Image.fromarray(rgb)

    buf = io.BytesIO()
    pil.save(buf, format="PNG")
    result = ocr.classification(buf.getvalue())

    digits = re.sub(r'\D', '', result)
    return digits, 0.95


# ── Master reader ─────────────────────────────────────────────
def read_meter(image_path: str, decimal_digits: int = 1, debug: bool = False) -> MeterReading:
    img_bgr, gray, processed = preprocess(image_path)
    dial = isolate_dial_region(img_bgr)

    if debug:
        from IPython.display import display
        import PIL.Image
        display(PIL.Image.fromarray(cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)))
        display(PIL.Image.fromarray(cv2.cvtColor(dial,    cv2.COLOR_BGR2RGB)))

    red_ranges = find_red_digit_columns(dial)

    # ── Try ddddocr on cropped dial ──────────────────────────
    raw_text, confidence, engine = "", 0.0, "none"
    try:
        raw_text, confidence = read_with_ddddocr(dial)
        engine = "ddddocr"
    except Exception as e:
        print(f"[WARN] ddddocr on dial failed: {e}")

    # ── Retry on thresholded image if empty ─────────────────
    if not re.sub(r'\D', '', raw_text):
        try:
            dial_gray3 = cv2.cvtColor(processed, cv2.COLOR_GRAY2BGR)
            raw_text, confidence = read_with_ddddocr(dial_gray3)
            engine = "ddddocr+thresh"
        except Exception as e:
            print(f"[WARN] ddddocr on thresh failed: {e}")

    digits = re.sub(r'\D', '', raw_text)
    print(f"[INFO] Engine: {engine} | Raw: '{raw_text}' | Digits: '{digits}'")

    # ── Auto-detect decimal digit count from red cells ───────
    # Overrides the passed-in decimal_digits with what's actually
    # visible as red in the image — gives correct split every time.
    if digits:
        detected_dec = count_red_digit_cells(dial, len(digits))
        if detected_dec > 0:
            decimal_digits = detected_dec
            print(f"[INFO] Auto-detected {decimal_digits} red (decimal) digit(s)")

    # ── Split integer / decimal ──────────────────────────────
    split_idx    = len(digits) - decimal_digits
    split_idx    = max(0, min(split_idx, len(digits)))   # clamp to valid range

    integer_part = digits[:split_idx] if split_idx > 0          else digits
    decimal_part = digits[split_idx:] if split_idx < len(digits) else ""

    # ── Build final value preserving leading zeros ───────────
    # e.g. digits="000819", integer="00081", decimal="9"
    # → full_value string = "00081.9"  (printed as-is, not as float)
    full_value_str = f"{integer_part}.{decimal_part}" if decimal_part else integer_part

    try:
        full_value = float(full_value_str)
    except ValueError:
        full_value = 0.0

    print(f"[INFO] Split → integer='{integer_part}'  decimal='{decimal_part}'  value='{full_value_str}'")

    return MeterReading(raw_text, integer_part, decimal_part, full_value, confidence)


print("✅ All functions loaded. Run Cell 3 to read your meter.")


# ============================================================
#  CELL 3 – Run on your image
# ============================================================

IMAGE_PATH     = "/home/akill-sud/Documents/projects/nagman_callibration/cropped_dataset/test/id_0289_meter_1_3.png"
DECIMAL_DIGITS = 1    # fallback if red-cell auto-detection finds nothing

reading = read_meter(IMAGE_PATH, decimal_digits=DECIMAL_DIGITS, debug=True)

# Build display string that preserves leading zeros (e.g. "00081.9")
display_value = f"{reading.integer_part}.{reading.decimal_part}" \
                if reading.decimal_part else reading.integer_part

print("\n" + "═" * 45)
print(f"  📟 Meter Reading  :  {display_value}")
print(f"  🔢 Integer part   :  {reading.integer_part}")
print(f"  🔴 Decimal part   :  {reading.decimal_part}")
print(f"  📊 OCR Confidence :  {reading.confidence:.2%}")
print("═" * 45)


# ============================================================
#  CELL 4 – Batch process a folder of images
# ============================================================

def batch_read(folder: str, decimal_digits: int = 1) -> list:
    results = []
    exts = (".jpg", ".jpeg", ".png", ".bmp")
    for p in sorted(Path(folder).iterdir()):
        if p.suffix.lower() in exts:
            try:
                r = read_meter(str(p), decimal_digits=decimal_digits)
                display_val = f"{r.integer_part}.{r.decimal_part}" \
                              if r.decimal_part else r.integer_part
                row = {"file": p.name, "value": display_val,
                       "integer": r.integer_part, "decimal": r.decimal_part,
                       "confidence": round(r.confidence, 3)}
                print(f"  ✓ {p.name:40s}  →  {display_val}  (conf={r.confidence:.2f})")
            except Exception as e:
                row = {"file": p.name, "value": None, "error": str(e)}
                print(f"  ✗ {p.name:40s}  →  ERROR: {e}")
            results.append(row)
    return results


results = batch_read(
    "/home/akill-sud/Documents/projects/nagman_callibration/cropped_dataset/test",
    decimal_digits=1
)

# Save to CSV (requires pandas):
# import pandas as pd
# pd.DataFrame(results).to_csv("meter_readings.csv", index=False)
# print("Saved to meter_readings.csv")


# In[ ]:





# In[ ]:





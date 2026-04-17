import os
import sys
import torch
from ultralytics import YOLO

os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "max_split_size_mb:128"

class StreamToCallback:
    def __init__(self, callback):
        self.callback = callback
        self.original_stdout = sys.stdout
        self.buffer = ""

    def write(self, msg):
        self.buffer += msg
        while '\n' in self.buffer:
            line, self.buffer = self.buffer.split('\n', 1)
            line_clean = line.strip()
            # Filter out tqdm progress bars and empty lines
            if line_clean and '\r' not in line and '━━━━━━━━━━━━' not in line_clean and '...' not in line_clean:
                # YOLO metrics output is useful, keep it.
                self.callback(line_clean)

        self.original_stdout.write(msg)

    def flush(self):
        self.original_stdout.flush()

def train_yolo(data_yaml, log_callback):
    device = "cuda" if torch.cuda.is_available() else "cpu"
    log_callback(f"Using device: {device}")

    if not os.path.exists("yolov8n.pt"):
        log_callback("ERROR: yolov8n.pt not found")
        return

    model = YOLO("yolov8n.pt")

    original_stdout = sys.stdout
    sys.stdout = StreamToCallback(log_callback)

    try:
        model.train(
            data=data_yaml,
            epochs=80,
            imgsz=512,
            batch=4,
            device=device,
            workers=2,
            amp=True,
            cache=False,
            optimizer="AdamW",
            lr0=0.001,
            lrf=0.01,
            mosaic=0.5,
            mixup=0.0,
            patience=15,
            cos_lr=True,
            verbose=True
        )
    finally:
        sys.stdout = original_stdout

    log_callback("Training completed successfully ✅")

import os
import torch
from ultralytics import YOLO

os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "max_split_size_mb:128"

def train_yolo(data_yaml, log_callback):
    device = "cuda" if torch.cuda.is_available() else "cpu"
    log_callback(f"Using device: {device}")

    if not os.path.exists("yolov8n.pt"):
        log_callback("ERROR: yolov8n.pt not found")
        return

    model = YOLO("yolov8n.pt")

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

    log_callback("Training completed successfully ✅")

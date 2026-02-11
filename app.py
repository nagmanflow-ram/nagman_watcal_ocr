from flask import Flask, render_template, request, jsonify, Response
import os, queue, threading, cv2, shutil, math
import requests

from ultralytics import YOLO
from train import train_yolo

import tensorflow as tf
from tensorflow.keras import layers, models
from tensorflow.keras.applications import InceptionV3
from tensorflow.keras.callbacks import EarlyStopping, ModelCheckpoint
from tensorflow.keras.models import load_model
from tensorflow.keras.preprocessing.image import ImageDataGenerator, load_img, img_to_array

import numpy as np
import matplotlib.pyplot as plt

# ---------------- GPU SETUP ----------------
gpus = tf.config.list_physical_devices('GPU')
if gpus:
    try:
        for gpu in gpus:
            tf.config.experimental.set_memory_growth(gpu, True)
        print(f"Using GPU(s): {gpus}")
    except RuntimeError as e:
        print(e)
else:
    print("No GPU found, using CPU.")

# ---------------- APP SETUP ----------------
app = Flask(__name__)

UPLOAD_FOLDER = "uploads"
STATIC_OUT = "static/output"

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(STATIC_OUT, exist_ok=True)

log_queue = queue.Queue()

def log(msg):
    log_queue.put(str(msg))

# ---------------- HOME ----------------
@app.route("/")
def index():
    return render_template("index.html", model_exists=os.path.exists("yolov8n.pt"))

# ---------------- YOLO TRAIN ----------------
@app.route("/upload", methods=["POST"])
def upload():
    file = request.files["data_yaml"]
    path = os.path.join(UPLOAD_FOLDER, "data.yaml")
    file.save(path)

    threading.Thread(
        target=train_yolo,
        args=(path, log),
        daemon=True
    ).start()

    return jsonify({"status": "YOLO training started"})

# ---------------- YOLO INFERENCE ----------------
@app.route("/run_inference", methods=["POST"])
def run_inference():
    d = request.json
    weights = d["weights"]
    image_dir = d["image_dir"]
    output_dir = d["output_dir"]

    def task():
        model = YOLO(weights)

        digital = os.path.join(output_dir, "digital")
        meters = os.path.join(output_dir, "meters")
        os.makedirs(digital, exist_ok=True)
        os.makedirs(meters, exist_ok=True)

        for f in os.listdir(image_dir):
            if not f.lower().endswith((".jpg", ".png", ".jpeg")):
                continue

            img_path = os.path.join(image_dir, f)
            img = cv2.imread(img_path)
            if img is None:
                continue

            results = model(img)

            for i, det in enumerate(results[0].boxes):
                x1, y1, x2, y2 = map(int, det.xyxy[0].tolist())
                roi = img[y1:y2, x1:x2]
                label = int(det.cls.item())
                name = os.path.splitext(f)[0]

                if label == 0:
                    cv2.imwrite(f"{digital}/{name}_{i}.png", roi)
                else:
                    cv2.imwrite(f"{meters}/{name}_{label}_{i}.png", roi)

        log("YOLO inference complete")

    threading.Thread(target=task, daemon=True).start()
    return jsonify({"status": "Inference started"})

# ---------------- MANUAL LABEL ----------------
@app.route("/manual_label", methods=["POST"])
def manual_label():
    img_dir = request.json["img_dir"]
    label_output_dir = request.json["label_output_dir"]

    def task():
        images = sorted([f for f in os.listdir(img_dir) if f.endswith(".png")])

        log(f"Manual labeling started | Source: {img_dir}")
        log(f"Target folders: {label_output_dir}/0-9")

        for img_name in images:
            path = os.path.join(img_dir, img_name)
            img = cv2.imread(path)
            if img is None:
                continue

            cv2.imshow("Press 0-9 to label | ESC to exit", img)
            key = cv2.waitKey(0) & 0xFF

            if ord('0') <= key <= ord('9'):
                label = chr(key)
                dst = os.path.join(label_output_dir, label, img_name)
                shutil.move(path, dst)
                log(f"{img_name} -> class {label}")

            elif key == 27:
                log("Manual labeling stopped by user")
                break

        cv2.destroyAllWindows()
        log("Manual labeling finished")

    threading.Thread(target=task, daemon=True).start()
    return jsonify({"status": "Manual labeling started"})

# ---------------- CNN TRAIN (InceptionV3 Rotary Model with GPU) ----------------
@app.route("/train_cnn", methods=["POST"])
def train_cnn():
    ROOT_DATA_DIR = request.json["data_dir"]  # folder with 0-9 subfolders
    SAVED_MODEL_FILE = "rotary_inception_best_model.keras"  # model saved here

    def task():
        IMG_HEIGHT = 299
        IMG_WIDTH = 299
        BATCH_SIZE = 32
        NUM_CLASSES = 10
        EPOCHS = 30

        # ImageDataGenerator with augmentation
        datagen = ImageDataGenerator(
            rescale=1./255,
            rotation_range=30,
            width_shift_range=0.2,
            height_shift_range=0.2,
            shear_range=0.2,
            zoom_range=0.2,
            horizontal_flip=True,
            fill_mode='nearest',
            validation_split=0.1
        )

        train_gen = datagen.flow_from_directory(
            ROOT_DATA_DIR,
            target_size=(IMG_HEIGHT, IMG_WIDTH),
            batch_size=BATCH_SIZE,
            class_mode='sparse',
            subset='training',
            shuffle=True
        )

        val_gen = datagen.flow_from_directory(
            ROOT_DATA_DIR,
            target_size=(IMG_HEIGHT, IMG_WIDTH),
            batch_size=BATCH_SIZE,
            class_mode='sparse',
            subset='validation',
            shuffle=False
        )

        # Pretrained InceptionV3
        base_model = InceptionV3(weights='imagenet', include_top=False,
                                 input_shape=(IMG_HEIGHT, IMG_WIDTH, 3))
        base_model.trainable = False

        model = models.Sequential([
            base_model,
            layers.GlobalAveragePooling2D(),
            layers.Dropout(0.5),
            layers.Dense(NUM_CLASSES, activation='softmax')
        ])

        model.compile(
            optimizer=tf.keras.optimizers.Adam(1e-4),
            loss='sparse_categorical_crossentropy',
            metrics=['accuracy']
        )

        callbacks = [
            EarlyStopping(monitor='val_loss', patience=5, restore_best_weights=True),
            ModelCheckpoint(SAVED_MODEL_FILE, monitor='val_loss', save_best_only=True)
        ]

        # Initial training
        model.fit(train_gen, validation_data=val_gen, epochs=10, callbacks=callbacks)

        # Fine-tune last 50 layers
        base_model.trainable = True
        for layer in base_model.layers[:-50]:
            layer.trainable = False

        model.compile(
            optimizer=tf.keras.optimizers.Adam(1e-5),
            loss='sparse_categorical_crossentropy',
            metrics=['accuracy']
        )

        model.fit(train_gen, validation_data=val_gen, epochs=EPOCHS, callbacks=callbacks)

        log(f"CNN training complete | Model saved as {SAVED_MODEL_FILE}")

    threading.Thread(target=task, daemon=True).start()
    return jsonify({"status": "CNN training started"})

# ---------------- CNN TEST ----------------
@app.route("/cnn_test", methods=["POST"])
def cnn_test():
    d = request.json
    MODEL_PATH = d["model_path"]
    TEST_DIR = d["test_dir"]

    def task():
        model = load_model(MODEL_PATH)
        IMG_HEIGHT = model.input_shape[1]
        IMG_WIDTH = model.input_shape[2]

        image_paths = []
        for root, _, files in os.walk(TEST_DIR):
            for f in files:
                if f.lower().endswith((".png", ".jpg", ".jpeg")):
                    image_paths.append(os.path.join(root, f))

        image_paths = image_paths[:20]
        rows = math.ceil(len(image_paths) / 5)

        plt.figure(figsize=(15, rows * 3))

        for i, img_path in enumerate(image_paths):
            img = image.load_img(img_path, target_size=(IMG_HEIGHT, IMG_WIDTH))
            arr = image.img_to_array(img)
            arr = np.expand_dims(arr, axis=0) / 255.0

            pred = model.predict(arr, verbose=0)
            pred_class = np.argmax(pred, axis=1)[0]

            plt.subplot(rows, 5, i + 1)
            plt.imshow(img)
            plt.title(f"Pred: {pred_class}")
            plt.axis("off")

        out_path = os.path.join(STATIC_OUT, "cnn_predictions.png")
        plt.tight_layout()
        plt.savefig(out_path)
        plt.close()

        log("CNN inference visualization saved")

    threading.Thread(target=task, daemon=True).start()
    return jsonify({"status": "CNN inference started"})

# ---------------- LOG STREAM ----------------
@app.route("/logs")
def logs():
    def stream():
        while True:
            yield f"data:{log_queue.get()}\n\n"
    return Response(stream(), mimetype="text/event-stream")

# ---------------- RUN ----------------
if __name__ == "__main__":
    app.run(debug=True)

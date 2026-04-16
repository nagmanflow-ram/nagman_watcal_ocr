import os
import time
os.environ["CUDA_VISIBLE_DEVICES"] = "0"

from flask import Flask, render_template, request, jsonify, Response
import queue, threading, cv2, shutil, math
import requests

from werkzeug.utils import secure_filename

from ultralytics import YOLO
from train import train_yolo

import tensorflow as tf
from tensorflow.keras import layers, models
from tensorflow.keras.applications import InceptionResNetV2
from tensorflow.keras.callbacks import EarlyStopping, ModelCheckpoint
from tensorflow.keras.models import load_model
from tensorflow.keras.preprocessing.image import (
    ImageDataGenerator,
    load_img,
    img_to_array
)

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

tf.keras.backend.set_floatx('float32')
tf.config.run_functions_eagerly(False)
tf.keras.utils.disable_interactive_logging()

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

# ---------------- SAFE CALLBACKS ----------------
class SafeLogsCallback(tf.keras.callbacks.Callback):
    def on_epoch_end(self, epoch, logs=None):
        if logs:
            for k, v in logs.items():
                if isinstance(v, tf.Tensor):
                    logs[k] = float(v.numpy())
                elif isinstance(v, (np.floating, np.float32, np.float64)):
                    logs[k] = float(v)

class SafeModelCheckpoint(ModelCheckpoint):
    def _save_model(self, epoch, batch, logs):
        if logs:
            for k, v in logs.items():
                if isinstance(v, tf.Tensor):
                    logs[k] = float(v.numpy())
                elif isinstance(v, (np.floating, np.float32, np.float64)):
                    logs[k] = float(v)
        super()._save_model(epoch, batch, logs)

# ---------------- APP SETUP ----------------
app = Flask(__name__)

UPLOAD_FOLDER = "uploads"
STATIC_OUT = "static/output"

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(STATIC_OUT, exist_ok=True)
os.makedirs(os.path.join(STATIC_OUT, "digital"), exist_ok=True)
os.makedirs(os.path.join(STATIC_OUT, "meters"), exist_ok=True)
os.makedirs(os.path.join(STATIC_OUT, "labeled_digital"), exist_ok=True)
os.makedirs(os.path.join(STATIC_OUT, "labeled_meters"), exist_ok=True)

log_queue = queue.Queue()
manual_label_running = False
manual_label_lock = threading.Lock()

def log(msg):
    log_queue.put(str(msg))

# ---------------- UTILS ----------------
def save_uploaded_files(files, run_dir, preserve_dirs=False):
    """Saves uploaded files to run_dir, returning count of saved files."""
    saved_count = 0
    for file in files:
        if file and file.filename:
            if preserve_dirs:
                # webkitdirectory paths: folder/subfolder/img.png
                parts = file.filename.replace('\\', '/').split('/')
                if len(parts) >= 2:
                    sub_dir = parts[-2]
                    fname = parts[-1]
                else:
                    sub_dir = ""
                    fname = parts[-1]
                
                target_dir = os.path.join(run_dir, sub_dir)
                os.makedirs(target_dir, exist_ok=True)
                file.save(os.path.join(target_dir, secure_filename(fname)))
            else:
                fname = os.path.basename(file.filename.replace('\\', '/'))
                file.save(os.path.join(run_dir, secure_filename(fname)))
            saved_count += 1
    return saved_count


# ---------------- ROUTES ----------------
@app.route("/")
def home():
    return render_template("home.html")

@app.route("/realtime")
def realtime():
    return render_template("realtime.html")

# =========================================================
# REALTIME Tracking CONFIG & MODELS
# =========================================================
YOLO_METER_MODEL = "/home/akill-sud/Documents/projects/nagman_callibration/runs/detect/train8/weights/best.pt"
YOLO_DIGIT_MODEL = "/home/akill-sud/Downloads/readings.yolov11/train/runs/detect/train3/weights/best.pt"
KERAS_MODEL = "/home/akill-sud/Documents/projects/yolo_web/rotary_inceptionresnet_best_model.keras"

KERAS_INDICES = [0, 2, 3]
STRIP_INDEX = 1
CLASSIFY_SIZE = 299
NUM_DIGITS = 6

realtime_models = {}

def get_realtime_models():
    if not realtime_models:
        import torch
        realtime_models['device'] = 0 if torch.cuda.is_available() else "cpu"
        realtime_models['meter_model'] = YOLO(YOLO_METER_MODEL)
        realtime_models['digit_model'] = YOLO(YOLO_DIGIT_MODEL)
        realtime_models['classifier_model'] = load_model(KERAS_MODEL)
        print("✅ All real-time tracking models loaded")
    return realtime_models

import imutils
import base64
import io

@app.route("/process_realtime", methods=["POST"])
def process_realtime():
    if 'image' not in request.files:
        return jsonify({"status": "error", "message": "No image uploaded"}), 400
        
    file = request.files['image']
    if file.filename == '':
        return jsonify({"status": "error", "message": "No selected file"}), 400

    try:
        models = get_realtime_models()
        meter_model = models['meter_model']
        digit_model = models['digit_model']
        classifier_model = models['classifier_model']
        device = models['device']

        # Load image from request
        in_memory_file = io.BytesIO()
        file.save(in_memory_file)
        data = np.frombuffer(in_memory_file.getvalue(), dtype=np.uint8)
        img = cv2.imdecode(data, cv2.IMREAD_COLOR)
        
        img = imutils.resize(img, width=800)
        img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

        # STEP 1: YOLO DETECTION
        results = meter_model(img)
        detections = results[0].boxes

        # Sort left -> right
        boxes = []
        for i, det in enumerate(detections):
            x1, y1, x2, y2 = map(int, det.xyxy[0].cpu().numpy())
            boxes.append((i, x1, y1, x2, y2))
        boxes = sorted(boxes, key=lambda x: x[1])

        # MODEL 2: KERAS CLASSIFICATION
        keras_preds = []
        keras_images = []

        for new_idx, (orig_idx, x1, y1, x2, y2) in enumerate(boxes):
            if new_idx not in KERAS_INDICES:
                continue

            pad = 5
            x1p, y1p = max(0, x1 - pad), max(0, y1 - pad)
            x2p, y2p = min(img.shape[1], x2 + pad), min(img.shape[0], y2 + pad)

            roi = img[y1p:y2p, x1p:x2p]
            keras_images.append((new_idx, roi))

            # In-memory preprocessing instead of saving to disk
            roi_resized = cv2.resize(roi, (CLASSIFY_SIZE, CLASSIFY_SIZE))
            roi_rgb = cv2.cvtColor(roi_resized, cv2.COLOR_BGR2RGB)
            img_array = roi_rgb.astype("float32") / 255.0
            img_array = np.expand_dims(img_array, axis=0)

            pred = classifier_model.predict(img_array, verbose=0)
            digit = np.argmax(pred)
            keras_preds.append((new_idx, digit))
            
        keras_preds = sorted(keras_preds, key=lambda x: x[0])
        keras_reading = "".join([str(x[1]) for x in keras_preds])

        # MODEL 3: DIGIT STRIP YOLO
        if len(boxes) <= STRIP_INDEX:
            return jsonify({"status": "error", "message": "Not enough detections for digit strip"}), 400

        _, x1, y1, x2, y2 = boxes[STRIP_INDEX]

        pad = 5
        x1, y1 = max(0, x1 - pad), max(0, y1 - pad)
        x2, y2 = min(img.shape[1], x2 + pad), min(img.shape[0], y2 + pad)

        strip_roi = img[y1:y2, x1:x2]

        def crop_digit_strip(image):
            h, w = image.shape[:2]
            return image[int(h*0.30):int(h*0.70), int(w*0.05):int(w*0.95)]

        digit_strip = crop_digit_strip(strip_roi)

        h, w = digit_strip.shape[:2]
        digit_width = w // NUM_DIGITS

        digits = []
        for i in range(NUM_DIGITS):
            digits.append(digit_strip[:, i*digit_width:(i+1)*digit_width])

        names = digit_model.names
        strip_preds = []

        for i, digit_img in enumerate(digits):
            d_res = digit_model.predict(source=digit_img, conf=0.25, device=device, verbose=False)
            digit_value = "?"
            for r in d_res:
                if len(r.boxes) > 0:
                    cls = int(r.boxes[0].cls[0])
                    digit_value = names[cls]
            strip_preds.append(digit_value)

        if len(strip_preds) == 6:
            strip_reading = "".join(strip_preds[:5]) + "." + strip_preds[5]
        else:
            strip_reading = "Invalid"

        final_output = f"{strip_reading}{keras_reading}"

        # VISUALIZATION
        plt.figure(figsize=(16,8))

        # Original
        plt.subplot(3,4,1)
        plt.imshow(img_rgb)
        plt.title("Original")
        plt.axis("off")

        # MODEL 2 VISUALS (Rotaries)
        for i, (idx, roi_img) in enumerate(keras_images):
            roi_rgb = cv2.cvtColor(roi_img, cv2.COLOR_BGR2RGB)
            pred_digit = [p[1] for p in keras_preds if p[0] == idx][0]

            plt.subplot(3,4,2+i)
            plt.imshow(roi_rgb)
            plt.title(f"Rotary: {pred_digit}")
            plt.axis("off")

        # Strip
        strip_rgb = cv2.cvtColor(digit_strip, cv2.COLOR_BGR2RGB)
        plt.subplot(3,4,6)
        plt.imshow(strip_rgb)
        plt.title("Meter Strip")
        plt.axis("off")

        # Digits
        for i, digit_img in enumerate(digits):
            digit_rgb = cv2.cvtColor(digit_img, cv2.COLOR_BGR2RGB)
            plt.subplot(3, NUM_DIGITS, 2*NUM_DIGITS + i + 1)
            plt.imshow(digit_rgb)
            plt.title(strip_preds[i])
            plt.axis("off")

        plt.suptitle(f"Final Output: {final_output}", fontsize=16)
        plt.tight_layout()

        # Save to buffer
        buf = io.BytesIO()
        plt.savefig(buf, format='png', bbox_inches='tight')
        plt.close()
        buf.seek(0)
        img_base64 = base64.b64encode(buf.read()).decode('utf-8')

        return jsonify({
            "status": "success",
            "strip_reading": strip_reading,
            "keras_reading": keras_reading,
            "final_output": final_output,
            "image_base64": img_base64
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/dashboard")
def dashboard():
    return render_template("dashboard.html", model_exists=os.path.exists("yolov8n.pt"))

@app.route("/ui/yolo_train")
def ui_yolo_train(): return render_template("yolo_train.html")

@app.route("/ui/yolo_inference")
def ui_yolo_inference(): return render_template("yolo_inference.html")

@app.route("/ui/manual_label")
def ui_manual_label(): return render_template("manual_label.html")

@app.route("/ui/meter_label")
def ui_meter_label(): return render_template("meter_label.html")

@app.route("/ui/cnn_train")
def ui_cnn_train(): return render_template("cnn_train.html")

@app.route("/ui/cnn_test")
def ui_cnn_test(): return render_template("cnn_test.html")

# ---------------- YOLO TRAIN ----------------
@app.route("/upload", methods=["POST"])
def upload():
    file = request.files.get("data_yaml")
    if not file:
        return jsonify({"status": "error", "message": "No data.yaml uploaded"})
    
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
    weights_file = request.files.get("weights")
    images = request.files.getlist("images")
    
    run_id = str(int(time.time()))
    run_dir = os.path.join(UPLOAD_FOLDER, f"infer_{run_id}")
    os.makedirs(run_dir, exist_ok=True)

    weights_path = "yolov8n.pt" # default fallback
    if weights_file and weights_file.filename:
        weights_path = os.path.join(run_dir, secure_filename(weights_file.filename))
        weights_file.save(weights_path)

    log(f"Saving uploaded images to {run_dir}...")
    saved_count = save_uploaded_files(images, run_dir, preserve_dirs=False)
    log(f"Saved {saved_count} images for inference.")

    def task():
        try:
            model = YOLO(weights_path)
            
            digital = os.path.join(STATIC_OUT, "digital")
            meters = os.path.join(STATIC_OUT, "meters")
            
            for f in os.listdir(run_dir):
                if not f.lower().endswith((".jpg", ".png", ".jpeg")):
                    continue
                    
                img_path = os.path.join(run_dir, f)
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
            
            log("YOLO inference complete Phase! Results auto-saved to output directory.")
        except Exception as e:
            log(f"Inference error: {e}")

    threading.Thread(target=task, daemon=True).start()
    return jsonify({"status": "Inference started"})

# ---------------- MANUAL LABEL ----------------
@app.route("/manual_label", methods=["POST"])
def manual_label():
    global manual_label_running
    with manual_label_lock:
        if manual_label_running:
            return jsonify({"status": "Manual labeling already running"})
        manual_label_running = True

    images = request.files.getlist("images")
    run_id = str(int(time.time()))
    img_dir = os.path.join(UPLOAD_FOLDER, f"manual_{run_id}")
    os.makedirs(img_dir, exist_ok=True)
    
    log("Saving uploaded digits for manual labeling...")
    saved_count = save_uploaded_files(images, img_dir, preserve_dirs=False)
    
    output_dir = os.path.join(STATIC_OUT, "labeled_digital")

    def task():
        global manual_label_running
        try:
            cv2.destroyAllWindows()
            if saved_count == 0:
                log("No images received for manual labeling.")
                return

            for i in range(10):
                os.makedirs(os.path.join(output_dir, str(i)), exist_ok=True)

            image_files = sorted([f for f in os.listdir(img_dir) if f.lower().endswith((".png", ".jpg", ".jpeg"))])
            log("Manual labeling started - Please check server window")

            for img_name in image_files:
                img_path = os.path.join(img_dir, img_name)
                img = cv2.imread(img_path)
                if img is None:
                    continue

                cv2.imshow("Manual Labeling - Press 0-9 | ESC to Exit", img)
                cv2.waitKey(1)
                key = cv2.waitKey(0)

                if key == 27:
                    log("Manual labeling stopped by user")
                    break

                if 48 <= key <= 57:
                    digit = chr(key)
                    dest_folder = os.path.join(output_dir, digit)
                    dest_path = os.path.join(dest_folder, img_name)
                    
                    base, ext = os.path.splitext(img_name)
                    counter = 1
                    while os.path.exists(dest_path):
                        dest_path = os.path.join(dest_folder, f"{base}_{counter}{ext}")
                        counter += 1
                        
                    shutil.move(img_path, dest_path)
                    log(f"Moved {img_name} labeled as {digit}")
                    
            log("Manual labeling completed Phase.")
        except Exception as e:
            log(f"Manual labeling error: {e}")
        finally:
            cv2.destroyAllWindows()
            with manual_label_lock:
                manual_label_running = False

    threading.Thread(target=task, daemon=True).start()
    return jsonify({"status": "Manual labeling started"})

# ---------------- METER LABELLING ----------------
@app.route("/meter_labelling", methods=["POST"])
def meter_labelling():
    global manual_label_running
    with manual_label_lock:
        if manual_label_running:
            return jsonify({"status": "Meter labeling already running"})
        manual_label_running = True

    images = request.files.getlist("images")
    run_id = str(int(time.time()))
    img_dir = os.path.join(UPLOAD_FOLDER, f"meter_label_{run_id}")
    os.makedirs(img_dir, exist_ok=True)
    
    log("Saving uploaded meters for labeling...")
    saved_count = save_uploaded_files(images, img_dir, preserve_dirs=False)
    
    output_dir = os.path.join(STATIC_OUT, "labeled_meters")
    NUM_DIGITS = 6

    def crop_digit_strip(image):
        h, w = image.shape[:2]
        return image[int(h * 0.30):int(h * 0.70), int(w * 0.05):int(w * 0.95)]

    def preprocess_digit(digit_img):
        gray = cv2.cvtColor(digit_img, cv2.COLOR_BGR2GRAY)
        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
        gray = clahe.apply(gray)
        thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)[1]
        kernel = np.ones((3, 3), np.uint8)
        thresh = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel)
        cnts, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if cnts:
            c = max(cnts, key=cv2.contourArea)
            x, y, w, h = cv2.boundingRect(c)
            thresh = thresh[y:y+h, x:x+w]
        thresh = cv2.resize(thresh, (64, 64))
        return thresh

    def split_digits(roi):
        h, w = roi.shape[:2]
        digit_width = w // NUM_DIGITS
        digits = []
        for i in range(NUM_DIGITS):
            digit_img = roi[:, i*digit_width:(i+1)*digit_width]
            digits.append(preprocess_digit(digit_img))
        return digits

    def save_digit_manually(digit_img, original_img, digit_strip):
        while True:
            cv2.imshow("Original Meter Image", original_img)
            cv2.imshow("Digit Strip", digit_strip)
            cv2.imshow("Current Digit (Press 0-9 to move, ESC to skip)", digit_img)
            key = cv2.waitKey(0) & 0xFF
            if ord('0') <= key <= ord('9'):
                label = chr(key)
                dst_dir = os.path.join(output_dir, label)
                os.makedirs(dst_dir, exist_ok=True)
                idx = len(os.listdir(dst_dir)) + 1
                file_path = os.path.join(dst_dir, f"{idx}.png")
                cv2.imwrite(file_path, digit_img)
                log(f"Moved digit {label} successfully.")
                break
            elif key == 27:
                break
        cv2.destroyAllWindows()

    def task():
        global manual_label_running
        try:
            if saved_count == 0:
                log("No images received for meter labeling.")
                return

            os.makedirs(output_dir, exist_ok=True)
            for i in range(10):
                os.makedirs(os.path.join(output_dir, str(i)), exist_ok=True)

            image_files = sorted([f for f in os.listdir(img_dir) if f.lower().endswith((".png", ".jpg", ".jpeg"))])
            for img_name in image_files:
                img_path = os.path.join(img_dir, img_name)
                image = cv2.imread(img_path)
                if image is None:
                    continue
                image = cv2.resize(image, (700, int(image.shape[0] * (700 / image.shape[1]))))
                digit_strip = crop_digit_strip(image)
                digits_list = split_digits(digit_strip)
                for digit_img in digits_list:
                    save_digit_manually(digit_img, image, digit_strip)
            log("Meter labeling completed Phase.")
        except Exception as e:
            log(f"Meter labeling error: {e}")
        finally:
            cv2.destroyAllWindows()
            with manual_label_lock:
                manual_label_running = False

    threading.Thread(target=task, daemon=True).start()
    return jsonify({"status": "Meter labeling started"})

# ---------------- CNN TRAIN ----------------
@app.route("/train_cnn", methods=["POST"])
def train_cnn():
    images = request.files.getlist("dataset")
    run_id = str(int(time.time()))
    dataset_dir = os.path.join(UPLOAD_FOLDER, f"cnn_train_{run_id}")
    os.makedirs(dataset_dir, exist_ok=True)
    
    log("Saving uploaded CNN dataset...")
    saved_count = save_uploaded_files(images, dataset_dir, preserve_dirs=True)
    log(f"Saved {saved_count} images for CNN training.")

    SAVED_MODEL_FILE = os.path.join(STATIC_OUT, "rotary_inceptionresnet_best_model.keras")

    def task():
        if saved_count == 0:
            log("Error: No dataset uploaded for CNN.")
            return

        IMG_HEIGHT, IMG_WIDTH = 299, 299
        BATCH_SIZE, NUM_CLASSES, EPOCHS = 32, 10, 40

        datagen = ImageDataGenerator(
            rescale=1./255, rotation_range=30, width_shift_range=0.2,
            height_shift_range=0.2, shear_range=0.2, zoom_range=0.2,
            horizontal_flip=True, fill_mode='nearest', validation_split=0.1
        )

        train_gen = datagen.flow_from_directory(
            dataset_dir, target_size=(IMG_HEIGHT, IMG_WIDTH), batch_size=BATCH_SIZE,
            class_mode='sparse', subset='training', shuffle=True
        )
        val_gen = datagen.flow_from_directory(
            dataset_dir, target_size=(IMG_HEIGHT, IMG_WIDTH), batch_size=BATCH_SIZE,
            class_mode='sparse', subset='validation', shuffle=False
        )

        base_model = InceptionResNetV2(weights='imagenet', include_top=False, input_shape=(IMG_HEIGHT, IMG_WIDTH, 3))
        base_model.trainable = False

        model = models.Sequential([
            base_model,
            layers.GlobalAveragePooling2D(), layers.BatchNormalization(),
            layers.Dropout(0.5), layers.Dense(512, activation='relu'),
            layers.Dropout(0.4), layers.Dense(NUM_CLASSES, activation='softmax')
        ])

        model.compile(optimizer=tf.keras.optimizers.Adam(1e-4), loss='sparse_categorical_crossentropy', metrics=['accuracy'])
        log("Phase 1: Training top layers...")
        model.fit(train_gen, validation_data=val_gen, epochs=15)

        log("Phase 2: Fine tuning deeper layers...")
        base_model.trainable = True
        for layer in base_model.layers[:-100]:
            layer.trainable = False

        model.compile(optimizer=tf.keras.optimizers.Adam(1e-5), loss='sparse_categorical_crossentropy', metrics=['accuracy'])
        model.fit(train_gen, validation_data=val_gen, epochs=EPOCHS)

        model.save(SAVED_MODEL_FILE)
        log(f"CNN training complete | Model saved successfully.")

        log("Phase 3: Testing model on validation data...")
        test_loss, test_acc = model.evaluate(val_gen, verbose=0)
        log(f"Model Evaluation -> Accuracy: {test_acc:.4f} | Loss: {test_loss:.4f}")

        log("Generating CNN testing visualization...")
        image_paths = []
        for root, dirs, files in os.walk(dataset_dir):
            for f in files:
                if f.lower().endswith((".png", ".jpg", ".jpeg")):
                    image_paths.append(os.path.join(root, f))
        
        if image_paths:
            import random
            random.shuffle(image_paths)
            sample_paths = image_paths[:20]
            rows = math.ceil(len(sample_paths) / 5)
            plt.figure(figsize=(15, rows * 3))

            class_indices = train_gen.class_indices
            idx_to_class = {v: k for k, v in class_indices.items()}

            for i, img_path in enumerate(sample_paths):
                img = load_img(img_path, target_size=(IMG_HEIGHT, IMG_WIDTH))
                arr = img_to_array(img)
                arr = np.expand_dims(arr, axis=0) / 255.0

                pred = model.predict(arr, verbose=0)
                pred_class = np.argmax(pred, axis=1)[0]
                pred_label = idx_to_class.get(pred_class, str(pred_class))

                plt.subplot(rows, 5, i + 1)
                plt.imshow(img)
                plt.title(f"Pred: {pred_label}")
                plt.axis("off")

            out_path = os.path.join(STATIC_OUT, "cnn_predictions.png")
            plt.tight_layout()
            plt.savefig(out_path)
            plt.close()
            log("CNN visualization saved and testing complete Phase.")

    threading.Thread(target=task, daemon=True).start()
    return jsonify({"status": "CNN training started"})

# ---------------- CNN TEST ----------------
@app.route("/cnn_test", methods=["POST"])
def cnn_test():
    model_file = request.files.get("model")
    images = request.files.getlist("images")
    
    run_id = str(int(time.time()))
    test_dir = os.path.join(UPLOAD_FOLDER, f"cnn_test_{run_id}")
    os.makedirs(test_dir, exist_ok=True)
    
    model_path = os.path.join(STATIC_OUT, "rotary_inceptionresnet_best_model.keras")
    if model_file and model_file.filename:
        model_path = os.path.join(test_dir, secure_filename(model_file.filename))
        model_file.save(model_path)
        
    save_uploaded_files(images, test_dir, preserve_dirs=False)

    def task():
        try:
            if not os.path.exists(model_path):
                log("Error: CNN Model not found for testing.")
                return

            model = load_model(model_path)
            IMG_HEIGHT, IMG_WIDTH = model.input_shape[1], model.input_shape[2]

            image_paths = [os.path.join(test_dir, f) for f in os.listdir(test_dir) if f.lower().endswith((".png", ".jpg", ".jpeg"))]
            if not image_paths:
                log("No images for CNN testing.")
                return

            image_paths = image_paths[:20]
            rows = math.ceil(len(image_paths) / 5)
            plt.figure(figsize=(15, rows * 3))

            for i, img_path in enumerate(image_paths):
                img = load_img(img_path, target_size=(IMG_HEIGHT, IMG_WIDTH))
                arr = img_to_array(img)
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
            log("CNN visualization saved and testing complete Phase.")
        except Exception as e:
            log(f"CNN testing error: {e}")

    threading.Thread(target=task, daemon=True).start()
    return jsonify({"status": "CNN test started"})

# ---------------- LOG STREAM ----------------
@app.route("/logs")
def logs():
    def generate():
        while True:
            msg = log_queue.get()
            yield f"data: {msg}\n\n"
    return Response(generate(), mimetype="text/event-stream")

if __name__ == "__main__":
    app.run(debug=True)

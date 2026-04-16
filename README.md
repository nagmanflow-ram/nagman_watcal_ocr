# Nagman Calibration & Meter Reading System

This project is a comprehensive end-to-end computer vision web application for reading, detecting, and managing analog and digital meter values. It provides powerful models and a user-friendly web interface allowing you to label data, train Convolutional Neural Networks (CNNs) and YOLO object detection models, and to do real-time tracking of readings.

## 🌟 Key Features Built In

### 1. Realtime Meter Tracking
- Automatically tracks dial and digital meters by using YOLO to detect the position of meters/digits. 
- Uses a pre-trained Keras CNN model (`InceptionResNetV2`) to recognize the exact readings on rotary dials, and YOLO to transcribe generic digital displays.
- Shows live, real-time plotting of the inferred values on user-uploaded images.

### 2. YOLO Detection & Training Pipelines
- **YOLO Training:** End-users can upload a `data.yaml` layout file directly via the web UI to initiate YOLO fine-tuning or training in the background.
- **YOLO Inference:** Feed images into the pre-trained `.pt` model parameters. It crops and sorts the components automatically in the `static/output` bins (e.g., separating digital strips from rotary meters).

### 3. Data Labeling Interfaces
- **Manual Labeling:** Once images are cropped by YOLO, this tool opens an interactive OpenCV window to manually tag digit values (0-9) via your keyboard into respective folders for highly localized datasets.
- **Meter Labeling Pipeline:** Advanced pipeline to auto-crop digit strips from complex meter bounds, and split them sequentially so a user can easily classify them interactively. 

### 4. CNN Image Classification Pipeline
- **CNN Training:** Allows users to upload their extracted datasets. It runs multi-phase transfer learning on `InceptionResNetV2` featuring dataset augmentation and freezing top-layers before fine-tuning deeper tiers for optimal accuracy.
- **CNN Testing:** Generates automated visual inference tests and predictions for rotary classifications, with accuracy metrics natively logged.

---

## 🚀 Running the Project

Follow these steps to safely run the website from your command line using the attached shell script.

### Method 1: Using the Automated Script
We have provided an automated script `start.sh` which automatically verifies your environment, installs dependencies, and runs the application, outputting precisely what it evaluates.
1. Give execution permission to the script:
   ```bash
   chmod +x start.sh
   ```
2. Run the script:
   ```bash
   ./start.sh
   ```

### Method 2: Manual Setup

**Step 1: Check Python Installation**
Ensure you have Python 3 installed. You can check this by running:
```bash
python3 --version
```
*(If Python is not installed, install it via your package manager. e.g. `sudo apt install python3`)*

**Step 2: Install Required Packages**
Install the core data-science and machine-learning libraries specified in the project requirements file:
```bash
pip install -r requirements.txt
```

**Step 3: Run the Server**
Once packages are fully downloaded, run the Flask backend:
```bash
python3 app.py
```
After executing, navigate to `http://127.0.0.1:5000` in your web browser. 

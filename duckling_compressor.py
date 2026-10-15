import os
import sys
import io
import zipfile

# Explicitly direct qt_material to PyQt5
os.environ["QT_API"] = "pyqt5"

import PyQt5
import PyQt5.QtCore
import PyQt5.QtGui
import PyQt5.QtWidgets
import PyQt5.QtSvg  # Enables Qt SVG icon rendering for qt_material

from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                             QPushButton, QLabel, QSlider, QComboBox, QCheckBox, QFileDialog, 
                             QListWidget, QListWidgetItem, QAbstractItemView, QProgressBar, 
                             QColorDialog, QDialog, QSpinBox, QMessageBox, QGroupBox, QLineEdit,
                             QStackedWidget, QPlainTextEdit)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QPixmap, QImage, QFontDatabase
from PIL import Image
from qt_material import apply_stylesheet, list_themes

VALID_IMAGE_EXTENSIONS = ('.png', '.jpg', '.jpeg', '.webp', '.bmp', '.tiff')

PRESET_DESKTOP_SIZES = {
    "1920 x 1080 (Full HD 1080p)": (1920, 1080),
    "2560 x 1440 (2K QHD)": (2560, 1440),
    "3840 x 2160 (4K UHD)": (3840, 2160),
    "1280 x 720 (HD 720p)": (1280, 720),
    "2560 x 1080 (Ultrawide)": (2560, 1080),
    "3440 x 1440 (21:9 Ultrawide)": (3440, 1440),
    "1366 x 768 (Laptop)": (1366, 768),
    "1024 x 768 (Standard)": (1024, 768)
}

def apply_image_resize(img, mode, pct, preset_size, custom_size, keep_aspect):
    if mode == "Percentage (%)":
        if pct != 100:
            new_w = max(1, int(img.width * (pct / 100.0)))
            new_h = max(1, int(img.height * (pct / 100.0)))
            return img.resize((new_w, new_h), Image.Resampling.LANCZOS)
    elif mode == "Desktop Preset":
        target_w, target_h = preset_size
        if keep_aspect:
            ratio = min(target_w / img.width, target_h / img.height)
            new_w = max(1, int(img.width * ratio))
            new_h = max(1, int(img.height * ratio))
        else:
            new_w, new_h = target_w, target_h
        return img.resize((new_w, new_h), Image.Resampling.LANCZOS)
    elif mode == "Custom Dimensions":
        target_w, target_h = custom_size
        if keep_aspect:
            ratio = min(target_w / img.width, target_h / img.height)
            new_w = max(1, int(img.width * ratio))
            new_h = max(1, int(img.height * ratio))
        else:
            new_w, new_h = target_w, target_h
        return img.resize((new_w, new_h), Image.Resampling.LANCZOS)
    return img


class ImageProcessorThread(QThread):
    progress = pyqtSignal(int)
    log = pyqtSignal(str)
    finished = pyqtSignal()

    def __init__(self, files, output_dir, quality, format_choice, 
                 resize_mode, resize_pct, preset_size, custom_size, keep_aspect,
                 enable_rename, rename_mode, base_text, rename_start, rename_padding,
                 custom_names_list, find_text, replace_text,
                 to_cbz, cbz_filename):
        super().__init__()
        self.files = files
        self.output_dir = output_dir
        self.quality = quality
        self.format_choice = format_choice
        self.resize_mode = resize_mode
        self.resize_pct = resize_pct
        self.preset_size = preset_size
        self.custom_size = custom_size
        self.keep_aspect = keep_aspect
        self.enable_rename = enable_rename
        self.rename_mode = rename_mode
        self.base_text = base_text
        self.rename_start = rename_start
        self.rename_padding = rename_padding
        self.custom_names_list = custom_names_list
        self.find_text = find_text
        self.replace_text = replace_text
        self.to_cbz = to_cbz
        self.cbz_filename = cbz_filename

    def run(self):
        total = len(self.files)
        if total == 0:
            self.finished.emit()
            return

        cbz_file = None
        if self.to_cbz:
            if not self.cbz_filename.lower().endswith('.cbz'):
                self.cbz_filename += '.cbz'
            cbz_path = os.path.join(self.output_dir, self.cbz_filename)
            try:
                cbz_file = zipfile.ZipFile(cbz_path, 'w', zipfile.ZIP_DEFLATED)
                self.log.emit(f"Creating CBZ archive: {self.cbz_filename}")
            except Exception as e:
                self.log.emit(f"Failed to create CBZ file: {str(e)}")
                self.finished.emit()
                return

        for i, file_path in enumerate(self.files):
            try:
                if not os.path.exists(file_path):
                    continue

                img = Image.open(file_path)
                
                # Apply Resize Strategy
                img = apply_image_resize(img, self.resize_mode, self.resize_pct, 
                                         self.preset_size, self.custom_size, self.keep_aspect)

                # Format Conversion
                original_format = img.format if img.format else "JPEG"
                out_format = self.format_choice if self.format_choice != "Original" else original_format
                
                if out_format.upper() in ["JPEG", "JPG"] and img.mode in ("RGBA", "P"):
                    img = img.convert("RGB")

                # Naming Logic
                if self.enable_rename:
                    if self.rename_mode == "Text + Numbering":
                        file_num = self.rename_start + i
                        num_str = str(file_num).zfill(self.rename_padding)
                        base_name = f"{self.base_text}{num_str}"
                    elif self.rename_mode == "Custom Names List":
                        if i < len(self.custom_names_list) and self.custom_names_list[i].strip():
                            base_name = self.custom_names_list[i].strip()
                        else:
                            filename = os.path.basename(file_path)
                            base_name, _ = os.path.splitext(filename)
                    elif self.rename_mode == "Find & Replace":
                        filename = os.path.basename(file_path)
                        base_name, _ = os.path.splitext(filename)
                        if self.find_text:
                            base_name = base_name.replace(self.find_text, self.replace_text)
                    out_filename = f"{base_name}.{out_format.lower()}"
                else:
                    filename = os.path.basename(file_path)
                    name, _ = os.path.splitext(filename)
                    out_filename = f"{name}.{out_format.lower()}"
                
                img_io = io.BytesIO()
                save_kwargs = {"format": out_format, "optimize": True}
                if out_format.upper() in ["JPEG", "JPG", "WEBP"]:
                    save_kwargs["quality"] = max(1, self.quality)

                img.save(img_io, **save_kwargs)
                img_data = img_io.getvalue()

                if self.to_cbz and cbz_file:
                    cbz_file.writestr(out_filename, img_data)
                    self.log.emit(f"Added to CBZ: {out_filename}")
                else:
                    out_path = os.path.join(self.output_dir, out_filename)
                    with open(out_path, "wb") as f:
                        f.write(img_data)
                    self.log.emit(f"Compressed & Saved: {out_filename}")

            except Exception as e:
                self.log.emit(f"Error processing {os.path.basename(file_path)}: {str(e)}")
            
            self.progress.emit(int(((i + 1) / total) * 100))

        if cbz_file:
            cbz_file.close()

        self.finished.emit()


class DragDropList(QListWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.accept()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls():
            event.setDropAction(Qt.CopyAction)
            event.accept()
        else:
            event.ignore()

    def dropEvent(self, event):
        if event.mimeData().hasUrls():
            event.setDropAction(Qt.CopyAction)
            event.accept()
            for url in event.mimeData().urls():
                if url.isLocalFile():
                    path = url.toLocalFile()
                    self.add_path(path)
        else:
            event.ignore()

    def add_path(self, path):
        if os.path.isdir(path):
            for root, _, files in os.walk(path):
                for file in sorted(files):
                    if file.lower().endswith(VALID_IMAGE_EXTENSIONS):
                        full_path = os.path.join(root, file)
                        if not self.is_duplicate(full_path):
                            self.addItem(full_path)
        elif os.path.isfile(path) and path.lower().endswith(VALID_IMAGE_EXTENSIONS):
            if not self.is_duplicate(path):
                self.addItem(path)

    def is_duplicate(self, file_path):
        for i in range(self.count()):
            if self.item(i).text() == file_path:
                return True
        return False


class PreviewDialog(QDialog):
    def __init__(self, file_path, quality, format_choice, resize_mode, resize_pct, preset_size, custom_size, keep_aspect):
        super().__init__()
        self.setWindowTitle("Duckling Image Compressor - Preview")
        self.resize(900, 600)
        self.layout = QHBoxLayout(self)

        self.orig_layout = QVBoxLayout()
        self.orig_label = QLabel("Original Image")
        self.orig_label.setAlignment(Qt.AlignCenter)
        self.orig_img = QLabel()
        self.orig_img.setAlignment(Qt.AlignCenter)
        
        orig_size = os.path.getsize(file_path) / 1024
        img_temp = Image.open(file_path)
        self.orig_info = QLabel(f"Original Size: {orig_size:.2f} KB\nDim: {img_temp.width} x {img_temp.height} px")
        self.orig_info.setAlignment(Qt.AlignCenter)
        
        self.orig_layout.addWidget(self.orig_label)
        self.orig_layout.addWidget(self.orig_img)
        self.orig_layout.addWidget(self.orig_info)

        self.new_layout = QVBoxLayout()
        self.new_label = QLabel("Compressed Estimate")
        self.new_label.setAlignment(Qt.AlignCenter)
        self.new_img = QLabel()
        self.new_img.setAlignment(Qt.AlignCenter)
        
        img = Image.open(file_path)
        img = apply_image_resize(img, resize_mode, resize_pct, preset_size, custom_size, keep_aspect)

        out_format = format_choice if format_choice != "Original" else (img.format or "JPEG")
        if out_format.upper() in ["JPEG", "JPG"] and img.mode in ("RGBA", "P"):
            img = img.convert("RGB")

        img_io = io.BytesIO()
        save_kwargs = {"format": out_format, "optimize": True}
        if out_format.upper() in ["JPEG", "JPG", "WEBP"]:
            save_kwargs["quality"] = max(1, quality)
        img.save(img_io, **save_kwargs)
        img_data = img_io.getvalue()
        
        new_size = len(img_data) / 1024
        savings = 100 - (new_size / orig_size * 100) if orig_size > 0 else 0
        
        self.new_info = QLabel(f"Est. Size: {new_size:.2f} KB ({savings:.1f}% saved)\nDim: {img.width} x {img.height} px")
        self.new_info.setAlignment(Qt.AlignCenter)

        self.new_layout.addWidget(self.new_label)
        self.new_layout.addWidget(self.new_img)
        self.new_layout.addWidget(self.new_info)

        qimg_orig = QImage(file_path)
        qpix_orig = QPixmap.fromImage(qimg_orig).scaled(400, 400, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.orig_img.setPixmap(qpix_orig)

        qimg_new = QImage.fromData(img_data)
        qpix_new = QPixmap.fromImage(qimg_new).scaled(400, 400, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.new_img.setPixmap(qpix_new)

        self.layout.addLayout(self.orig_layout)
        self.layout.addLayout(self.new_layout)


class DucklingImageCompressorApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Duckling Image Compressor")
        self.resize(1100, 850)
        self.output_dir = os.path.expanduser("~/Desktop")
        self.text_color = None
        self.initUI()
        
    def initUI(self):
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QHBoxLayout(main_widget)

        # LEFT PANEL: File List & Queue Buttons
        left_panel = QVBoxLayout()
        self.file_list = DragDropList()
        left_panel.addWidget(QLabel("Drag & Drop Files or Folders Here:"))
        left_panel.addWidget(self.file_list)
        
        btn_layout = QHBoxLayout()
        self.add_btn = QPushButton("Add Files")
        self.add_btn.clicked.connect(self.add_files)
        
        self.add_folder_btn = QPushButton("Add Folder")
        self.add_folder_btn.clicked.connect(self.add_folder)

        self.preview_btn = QPushButton("Preview Selected")
        self.preview_btn.clicked.connect(self.preview_image)

        self.clear_btn = QPushButton("Clear List")
        self.clear_btn.clicked.connect(self.file_list.clear)
        
        btn_layout.addWidget(self.add_btn)
        btn_layout.addWidget(self.add_folder_btn)
        btn_layout.addWidget(self.preview_btn)
        btn_layout.addWidget(self.clear_btn)
        left_panel.addLayout(btn_layout)
        
        # RIGHT PANEL: Options & Controls
        right_panel = QVBoxLayout()
        
        # 1. Output Folder
        loc_group = QGroupBox("Output Location")
        loc_layout = QHBoxLayout()
        self.loc_label = QLabel(self.output_dir)
        self.loc_btn = QPushButton("Change")
        self.loc_btn.clicked.connect(self.change_output_dir)
        loc_layout.addWidget(self.loc_label)
        loc_layout.addWidget(self.loc_btn)
        loc_group.setLayout(loc_layout)
        right_panel.addWidget(loc_group)

        # 2. Compression & Resizing
        settings_group = QGroupBox("Compression & Resize Options")
        settings_layout = QVBoxLayout()
        
        self.slider_label = QLabel("Compression Level: 0 (Same Quality)")
        self.quality_slider = QSlider(Qt.Horizontal)
        self.quality_slider.setRange(0, 99)
        self.quality_slider.setValue(0)
        self.quality_slider.valueChanged.connect(self.update_slider_label)
        settings_layout.addWidget(self.slider_label)
        settings_layout.addWidget(self.quality_slider)
        
        format_layout = QHBoxLayout()
        format_layout.addWidget(QLabel("Convert to Format:"))
        self.format_combo = QComboBox()
        self.format_combo.addItems(["Original", "JPEG", "PNG", "WEBP", "BMP", "TIFF"])
        self.format_combo.currentTextChanged.connect(self.update_rename_preview)
        format_layout.addWidget(self.format_combo)
        settings_layout.addLayout(format_layout)
        
        # Resizing Modes
        resize_mode_layout = QHBoxLayout()
        resize_mode_layout.addWidget(QLabel("Resize Mode:"))
        self.resize_mode_combo = QComboBox()
        self.resize_mode_combo.addItems(["Original Size", "Percentage (%)", "Desktop Preset", "Custom Dimensions"])
        self.resize_mode_combo.currentTextChanged.connect(self.on_resize_mode_change)
        resize_mode_layout.addWidget(self.resize_mode_combo)
        settings_layout.addLayout(resize_mode_layout)

        # Stacked Widget for Resize Controls
        self.resize_stack = QStackedWidget()

        # Page 0: Original Size
        page_none = QWidget()
        self.resize_stack.addWidget(page_none)

        # Page 1: Percentage
        page_pct = QWidget()
        layout_pct = QHBoxLayout(page_pct)
        layout_pct.setContentsMargins(0, 5, 0, 5)
        layout_pct.addWidget(QLabel("Scale (%):"))
        self.resize_pct_spin = QSpinBox()
        self.resize_pct_spin.setRange(1, 500)
        self.resize_pct_spin.setValue(100)
        layout_pct.addWidget(self.resize_pct_spin)
        self.resize_stack.addWidget(page_pct)

        # Page 2: Desktop Presets
        page_preset = QWidget()
        layout_preset = QHBoxLayout(page_preset)
        layout_preset.setContentsMargins(0, 5, 0, 5)
        layout_preset.addWidget(QLabel("Preset Size:"))
        self.preset_combo = QComboBox()
        self.preset_combo.addItems(list(PRESET_DESKTOP_SIZES.keys()))
        layout_preset.addWidget(self.preset_combo)
        self.resize_stack.addWidget(page_preset)

        # Page 3: Custom Dimensions
        page_custom = QWidget()
        layout_custom = QHBoxLayout(page_custom)
        layout_custom.setContentsMargins(0, 5, 0, 5)
        layout_custom.addWidget(QLabel("Width (px):"))
        self.custom_w_spin = QSpinBox()
        self.custom_w_spin.setRange(1, 10000)
        self.custom_w_spin.setValue(1920)
        layout_custom.addWidget(self.custom_w_spin)
        
        layout_custom.addWidget(QLabel("Height (px):"))
        self.custom_h_spin = QSpinBox()
        self.custom_h_spin.setRange(1, 10000)
        self.custom_h_spin.setValue(1080)
        layout_custom.addWidget(self.custom_h_spin)
        self.resize_stack.addWidget(page_custom)

        settings_layout.addWidget(self.resize_stack)

        self.keep_aspect_check = QCheckBox("Maintain Aspect Ratio (For Presets & Custom Sizes)")
        self.keep_aspect_check.setChecked(True)
        self.keep_aspect_check.setVisible(False)
        settings_layout.addWidget(self.keep_aspect_check)

        # CBZ Archive Toggle
        cbz_layout = QVBoxLayout()
        self.cbz_check = QCheckBox("Package outputs into a single .CBZ archive")
        self.cbz_check.setChecked(False)
        self.cbz_check.toggled.connect(self.toggle_cbz_input)
        
        cbz_name_layout = QHBoxLayout()
        self.cbz_name_label = QLabel("Archive Name:")
        self.cbz_name_input = QLineEdit("Duckling_Archive")
        self.cbz_name_label.setEnabled(False)
        self.cbz_name_input.setEnabled(False)
        
        cbz_name_layout.addWidget(self.cbz_name_label)
        cbz_name_layout.addWidget(self.cbz_name_input)
        cbz_layout.addWidget(self.cbz_check)
        cbz_layout.addLayout(cbz_name_layout)
        settings_layout.addLayout(cbz_layout)

        settings_group.setLayout(settings_layout)
        right_panel.addWidget(settings_group)

        # 3. Bulk Batch Renamer Group
        rename_group = QGroupBox("Bulk Batch Renaming")
        rename_layout = QVBoxLayout()
        
        self.rename_check = QCheckBox("Enable Batch File Renaming")
        self.rename_check.setChecked(False)
        self.rename_check.toggled.connect(self.toggle_rename_inputs)
        rename_layout.addWidget(self.rename_check)

        rename_mode_layout = QHBoxLayout()
        rename_mode_layout.addWidget(QLabel("Rename Mode:"))
        self.rename_mode_combo = QComboBox()
        self.rename_mode_combo.addItems(["Text + Numbering", "Custom Names List", "Find & Replace"])
        self.rename_mode_combo.setEnabled(False)
        self.rename_mode_combo.currentTextChanged.connect(self.on_rename_mode_change)
        rename_mode_layout.addWidget(self.rename_mode_combo)
        rename_layout.addLayout(rename_mode_layout)

        # Stacked Widget for Renamer Options
        self.rename_stack = QStackedWidget()

        # Rename Page 0: Text + Numbering (e.g. rabbit01.png, rabbit02.png)
        page_seq = QWidget()
        layout_seq = QHBoxLayout(page_seq)
        layout_seq.setContentsMargins(0, 5, 0, 5)
        
        layout_seq.addWidget(QLabel("Text Name:"))
        self.base_text_input = QLineEdit("rabbit")
        self.base_text_input.setEnabled(False)
        self.base_text_input.textChanged.connect(self.update_rename_preview)
        layout_seq.addWidget(self.base_text_input)

        layout_seq.addWidget(QLabel("Start #:"))
        self.rename_start_spin = QSpinBox()
        self.rename_start_spin.setRange(1, 9999)
        self.rename_start_spin.setValue(1)
        self.rename_start_spin.setEnabled(False)
        self.rename_start_spin.valueChanged.connect(self.update_rename_preview)
        layout_seq.addWidget(self.rename_start_spin)

        layout_seq.addWidget(QLabel("Digits:"))
        self.rename_padding_spin = QSpinBox()
        self.rename_padding_spin.setRange(1, 8)
        self.rename_padding_spin.setValue(2)  # Default 2 digits e.g. 01, 02
        self.rename_padding_spin.setEnabled(False)
        self.rename_padding_spin.valueChanged.connect(self.update_rename_preview)
        layout_seq.addWidget(self.rename_padding_spin)
        self.rename_stack.addWidget(page_seq)

        # Rename Page 1: Custom Names List (Comma/Line separated)
        page_custom_list = QWidget()
        layout_c_list = QVBoxLayout(page_custom_list)
        layout_c_list.setContentsMargins(0, 5, 0, 5)
        layout_c_list.addWidget(QLabel("Names List (comma or line separated):"))
        self.custom_list_input = QPlainTextEdit("text1, text2, text3")
        self.custom_list_input.setMaximumHeight(60)
        self.custom_list_input.setEnabled(False)
        self.custom_list_input.textChanged.connect(self.update_rename_preview)
        layout_c_list.addWidget(self.custom_list_input)
        self.rename_stack.addWidget(page_custom_list)

        # Rename Page 2: Find & Replace
        page_fr = QWidget()
        layout_fr = QHBoxLayout(page_fr)
        layout_fr.setContentsMargins(0, 5, 0, 5)
        layout_fr.addWidget(QLabel("Find:"))
        self.find_text_input = QLineEdit("dog")
        self.find_text_input.setEnabled(False)
        self.find_text_input.textChanged.connect(self.update_rename_preview)
        layout_fr.addWidget(self.find_text_input)

        layout_fr.addWidget(QLabel("Replace:"))
        self.replace_text_input = QLineEdit("text1")
        self.replace_text_input.setEnabled(False)
        self.replace_text_input.textChanged.connect(self.update_rename_preview)
        layout_fr.addWidget(self.replace_text_input)
        self.rename_stack.addWidget(page_fr)

        rename_layout.addWidget(self.rename_stack)

        self.rename_preview_label = QLabel("Example Output: rabbit01.png")
        self.rename_preview_label.setStyleSheet("font-style: italic; opacity: 0.8;")
        rename_layout.addWidget(self.rename_preview_label)

        rename_group.setLayout(rename_layout)
        right_panel.addWidget(rename_group)

        # 4. Themes & Customization
        app_group = QGroupBox("Appearance & Themes")
        app_layout = QVBoxLayout()
        
        theme_layout = QHBoxLayout()
        theme_layout.addWidget(QLabel("Theme:"))
        self.theme_combo = QComboBox()
        themes = list_themes()
        if not themes:
            themes = ['dark_teal.xml', 'dark_amber.xml', 'dark_blue.xml', 'dark_cyan.xml', 
                      'dark_lightgreen.xml', 'dark_pink.xml', 'dark_purple.xml', 'dark_red.xml', 
                      'light_amber.xml', 'light_blue.xml', 'light_cyan.xml', 'light_teal.xml']
        self.theme_combo.addItems(themes)
        self.theme_combo.currentTextChanged.connect(self.change_theme)
        theme_layout.addWidget(self.theme_combo)
        app_layout.addLayout(theme_layout)
        
        self.color_btn = QPushButton("Override Text Color")
        self.color_btn.clicked.connect(self.change_text_color)
        app_layout.addWidget(self.color_btn)
        
        app_group.setLayout(app_layout)
        right_panel.addWidget(app_group)
        
        # Action Buttons & Status
        right_panel.addStretch()
        self.process_btn = QPushButton("Start Processing")
        self.process_btn.setMinimumHeight(50)
        self.process_btn.setStyleSheet("font-weight: bold; font-size: 16px;")
        self.process_btn.clicked.connect(self.start_processing)
        right_panel.addWidget(self.process_btn)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        right_panel.addWidget(self.progress_bar)

        self.status_label = QLabel("Ready")
        right_panel.addWidget(self.status_label)
        
        main_layout.addLayout(left_panel, 3)
        main_layout.addLayout(right_panel, 2)

    def on_resize_mode_change(self, mode):
        if mode == "Original Size":
            self.resize_stack.setCurrentIndex(0)
            self.keep_aspect_check.setVisible(False)
        elif mode == "Percentage (%)":
            self.resize_stack.setCurrentIndex(1)
            self.keep_aspect_check.setVisible(False)
        elif mode == "Desktop Preset":
            self.resize_stack.setCurrentIndex(2)
            self.keep_aspect_check.setVisible(True)
        elif mode == "Custom Dimensions":
            self.resize_stack.setCurrentIndex(3)
            self.keep_aspect_check.setVisible(True)

    def on_rename_mode_change(self, mode):
        if mode == "Text + Numbering":
            self.rename_stack.setCurrentIndex(0)
        elif mode == "Custom Names List":
            self.rename_stack.setCurrentIndex(1)
        elif mode == "Find & Replace":
            self.rename_stack.setCurrentIndex(2)
        self.update_rename_preview()

    def update_slider_label(self, value):
        if value == 0:
            text = "0 (Same Quality / Minimal Compression)"
        elif value == 99:
            text = "Max Compression (Lowest Quality)"
        else:
            text = f"{value}% Compressed"
        self.slider_label.setText(f"Compression Level: {text}")

    def toggle_cbz_input(self, checked):
        self.cbz_name_label.setEnabled(checked)
        self.cbz_name_input.setEnabled(checked)

    def toggle_rename_inputs(self, checked):
        self.rename_mode_combo.setEnabled(checked)
        self.base_text_input.setEnabled(checked)
        self.rename_start_spin.setEnabled(checked)
        self.rename_padding_spin.setEnabled(checked)
        self.custom_list_input.setEnabled(checked)
        self.find_text_input.setEnabled(checked)
        self.replace_text_input.setEnabled(checked)
        self.update_rename_preview()

    def parse_custom_names(self):
        raw_text = self.custom_list_input.toPlainText()
        names = []
        for line in raw_text.replace(',', '\n').split('\n'):
            cleaned = line.strip()
            if cleaned:
                names.append(cleaned)
        return names

    def update_rename_preview(self):
        if self.rename_check.isChecked():
            mode = self.rename_mode_combo.currentText()
            fmt = self.format_combo.currentText().lower()
            if fmt == "original":
                fmt = "png"

            if mode == "Text + Numbering":
                base_txt = self.base_text_input.text().strip() or "rabbit"
                start = self.rename_start_spin.value()
                padding = self.rename_padding_spin.value()
                num_str = str(start).zfill(padding)
                self.rename_preview_label.setText(f"Example Output: {base_txt}{num_str}.{fmt}")
            elif mode == "Custom Names List":
                names = self.parse_custom_names()
                example = names[0] if names else "text1"
                self.rename_preview_label.setText(f"Example Output: {example}.{fmt}")
            elif mode == "Find & Replace":
                find_txt = self.find_text_input.text()
                replace_txt = self.replace_text_input.text()
                self.rename_preview_label.setText(f"Replaces '{find_txt}' with '{replace_txt}'.{fmt}")
        else:
            self.rename_preview_label.setText("Batch renaming disabled (keeps original file names)")

    def add_files(self):
        files, _ = QFileDialog.getOpenFileNames(
            self, "Select Images", "", 
            "Images (*.png *.jpg *.jpeg *.webp *.bmp *.tiff)"
        )
        for f in files:
            self.file_list.add_path(f)

    def add_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Folder with Images")
        if folder:
            self.file_list.add_path(folder)

    def change_output_dir(self):
        d = QFileDialog.getExistingDirectory(self, "Select Output Directory", self.output_dir)
        if d:
            self.output_dir = d
            self.loc_label.setText(self.output_dir)

    def change_theme(self, theme_name):
        try:
            apply_stylesheet(app, theme=theme_name)
        except Exception as e:
            print(f"Failed to change theme: {e}")
            
        if self.text_color:
            self.apply_custom_text_color()

    def change_text_color(self):
        color = QColorDialog.getColor()
        if color.isValid():
            self.text_color = color.name()
            self.apply_custom_text_color()

    def apply_custom_text_color(self):
        if self.text_color:
            self.setStyleSheet(f"QWidget {{ color: {self.text_color} !important; }}")

    def get_resize_parameters(self):
        mode = self.resize_mode_combo.currentText()
        pct = self.resize_pct_spin.value()
        preset_name = self.preset_combo.currentText()
        preset_size = PRESET_DESKTOP_SIZES.get(preset_name, (1920, 1080))
        custom_size = (self.custom_w_spin.value(), self.custom_h_spin.value())
        keep_aspect = self.keep_aspect_check.isChecked()
        return mode, pct, preset_size, custom_size, keep_aspect

    def preview_image(self):
        if self.file_list.count() == 0:
            QMessageBox.warning(self, "Error", "Please add images to preview.")
            return
            
        selected = self.file_list.selectedItems()
        item = selected[0] if selected else self.file_list.item(0)
        
        pil_quality = 100 - self.quality_slider.value()
        mode, pct, preset_size, custom_size, keep_aspect = self.get_resize_parameters()
        
        preview = PreviewDialog(
            item.text(), 
            pil_quality, 
            self.format_combo.currentText(), 
            mode, pct, preset_size, custom_size, keep_aspect
        )
        preview.exec_()

    def start_processing(self):
        if self.file_list.count() == 0:
            QMessageBox.warning(self, "Error", "No images in queue to process.")
            return

        files = [self.file_list.item(i).text() for i in range(self.file_list.count())]
        pil_quality = 100 - self.quality_slider.value()
        fmt = self.format_combo.currentText()
        
        mode, pct, preset_size, custom_size, keep_aspect = self.get_resize_parameters()
        
        enable_rename = self.rename_check.isChecked()
        rename_mode = self.rename_mode_combo.currentText()
        base_text = self.base_text_input.text().strip() or "rabbit"
        rename_start = self.rename_start_spin.value()
        rename_padding = self.rename_padding_spin.value()
        custom_names_list = self.parse_custom_names()
        find_text = self.find_text_input.text()
        replace_text = self.replace_text_input.text()

        to_cbz = self.cbz_check.isChecked()
        cbz_name = self.cbz_name_input.text().strip() or "Duckling_Archive"

        self.process_btn.setEnabled(False)
        self.progress_bar.setValue(0)
        
        self.thread = ImageProcessorThread(
            files, self.output_dir, pil_quality, fmt,
            mode, pct, preset_size, custom_size, keep_aspect,
            enable_rename, rename_mode, base_text, rename_start, rename_padding,
            custom_names_list, find_text, replace_text,
            to_cbz, cbz_name
        )
        self.thread.progress.connect(self.progress_bar.setValue)
        self.thread.log.connect(self.status_label.setText)
        self.thread.finished.connect(self.processing_finished)
        self.thread.start()

    def processing_finished(self):
        self.process_btn.setEnabled(True)
        self.status_label.setText("Processing Complete!")
        QMessageBox.information(self, "Success", f"All images successfully processed!\n\nSaved to:\n{self.output_dir}")


if __name__ == '__main__':
    app = QApplication(sys.argv)
    
    try:
        apply_stylesheet(app, theme='dark_teal.xml')
    except Exception as e:
        print(f"Initial theme load error: {e}")
    
    window = DucklingImageCompressorApp()
    window.show()
    sys.exit(app.exec_())

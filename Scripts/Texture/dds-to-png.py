"""
https://github.com/saidipo/DDS-PNG-PNG-DDS-Converter
Author: Mohamed Saidi

"""
import sys
import os
from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton, QFileDialog, QVBoxLayout,
    QMessageBox, QRadioButton, QCheckBox, QSpinBox, QComboBox, QGroupBox, QFormLayout
)
from PyQt5.QtCore import Qt
from PIL import Image, ImageFilter, ImageEnhance
from PyQt5.QtGui import QIcon

def apply_image_filters(image, brightness, contrast, saturation, sharpening, blurring):
    if sharpening:
        enhancer = ImageEnhance.Sharpness(image)
        image = enhancer.enhance(2.0)
    if blurring:
        image = image.filter(ImageFilter.BLUR)
    if brightness != 0:
        enhancer = ImageEnhance.Brightness(image)
        image = enhancer.enhance(1 + brightness / 100.0)
    if contrast != 0:
        enhancer = ImageEnhance.Contrast(image)
        image = enhancer.enhance(1 + contrast / 100.0)
    if saturation != 1:
        enhancer = ImageEnhance.Color(image)
        image = enhancer.enhance(saturation / 100.0)
    return image

def convert_dds_to_png(dds_directory, png_directory, compression_type='lossless', keep_alpha=True, resize=None, brightness=0, contrast=0, saturation=1, sharpening=False, blurring=False):
    if not os.path.exists(png_directory):
        os.makedirs(png_directory)
    for filename in os.listdir(dds_directory):
        if filename.endswith('.dds'):
            dds_path = os.path.join(dds_directory, filename)
            png_filename = os.path.splitext(filename)[0] + '.png'
            png_path = os.path.join(png_directory, png_filename)
            image = Image.open(dds_path)
            if not keep_alpha and image.mode == 'RGBA':
                image = image.convert('RGB')
            if resize:
                image = image.resize(resize, Image.LANCZOS)
            image = apply_image_filters(image, brightness, contrast, saturation, sharpening, blurring)
            if compression_type == 'lossy':
                image.save(png_path, format='PNG', compress_level=6)
            else:
                image.save(png_path, format='PNG', compress_level=0)

def convert_png_to_dds(png_directory, dds_directory, keep_alpha=True):
    if not os.path.exists(dds_directory):
        os.makedirs(dds_directory)
    for filename in os.listdir(png_directory):
        if filename.endswith('.png'):
            png_path = os.path.join(png_directory, filename)
            dds_filename = os.path.splitext(filename)[0] + '.dds'
            dds_path = os.path.join(dds_directory, dds_filename)
            image = Image.open(png_path)
            if not keep_alpha and image.mode == 'RGBA':
                image = image.convert('RGB')
            image.save(dds_path, format='DDS')

class ConverterApp(QWidget):
    def __init__(self):
        super().__init__()
        self.initUI()

    def initUI(self):
        layout = QVBoxLayout()
        self.setWindowIcon(QIcon('icon.png'))
        self.dds_to_png_radio = QRadioButton("DDS to PNG")
        self.dds_to_png_radio.setChecked(True)
        self.png_to_dds_radio = QRadioButton("PNG to DDS")
        layout.addWidget(self.dds_to_png_radio)
        layout.addWidget(self.png_to_dds_radio)
        self.source_dir_label = QLabel("Source Directory:")
        self.source_dir_button = QPushButton("Browse")
        self.source_dir_button.clicked.connect(self.select_source_directory)
        layout.addWidget(self.source_dir_label)
        layout.addWidget(self.source_dir_button)
        self.output_dir_label = QLabel("Output Directory:")
        self.output_dir_button = QPushButton("Browse")
        self.output_dir_button.clicked.connect(self.select_output_directory)
        layout.addWidget(self.output_dir_label)
        layout.addWidget(self.output_dir_button)
        self.advanced_checkbox = QCheckBox("Enable Advanced Settings (Only DDS TO PNG)")
        self.advanced_checkbox.stateChanged.connect(self.toggle_advanced_settings)
        layout.addWidget(self.advanced_checkbox)
        self.advanced_group = QGroupBox("Advanced Settings")
        self.advanced_group.setCheckable(False)
        self.advanced_group.setEnabled(False)
        advanced_layout = QFormLayout()
        self.resize_checkbox = QCheckBox("Enable Resize Output")
        advanced_layout.addRow(self.resize_checkbox)
        self.resize_width_spinbox = QSpinBox()
        self.resize_width_spinbox.setRange(16, 4096)
        self.resize_width_spinbox.setValue(0)
        self.resize_height_spinbox = QSpinBox()
        self.resize_height_spinbox.setRange(16, 4096)
        self.resize_height_spinbox.setValue(0)
        advanced_layout.addRow("Resize Width:", self.resize_width_spinbox)
        advanced_layout.addRow("Resize Height:", self.resize_height_spinbox)
        self.brightness_checkbox = QCheckBox("Enable Brightness Adjustment")
        self.brightness_spinbox = QSpinBox()
        self.brightness_spinbox.setRange(-100, 100)
        self.brightness_spinbox.setValue(0)
        advanced_layout.addRow(self.brightness_checkbox)
        advanced_layout.addRow("Brightness:", self.brightness_spinbox)
        self.contrast_checkbox = QCheckBox("Enable Contrast Adjustment")
        self.contrast_spinbox = QSpinBox()
        self.contrast_spinbox.setRange(-100, 100)
        self.contrast_spinbox.setValue(0)
        advanced_layout.addRow(self.contrast_checkbox)
        advanced_layout.addRow("Contrast:", self.contrast_spinbox)
        self.saturation_checkbox = QCheckBox("Enable Saturation Adjustment")
        self.saturation_spinbox = QSpinBox()
        self.saturation_spinbox.setRange(0, 200)
        self.saturation_spinbox.setValue(100)
        advanced_layout.addRow(self.saturation_checkbox)
        advanced_layout.addRow("Saturation:", self.saturation_spinbox)
        self.sharpening_checkbox = QCheckBox("Enable Sharpening")
        self.sharpening_enabled_checkbox = QCheckBox("Apply Sharpening")
        advanced_layout.addRow(self.sharpening_checkbox)
        advanced_layout.addRow(self.sharpening_enabled_checkbox)
        self.blurring_checkbox = QCheckBox("Enable Blurring")
        self.blurring_enabled_checkbox = QCheckBox("Apply Blurring")
        advanced_layout.addRow(self.blurring_checkbox)
        advanced_layout.addRow(self.blurring_enabled_checkbox)
        self.png_compression_checkbox = QCheckBox("Enable PNG Compression Type")
        self.png_compression_type_combobox = QComboBox()
        self.png_compression_type_combobox.addItems(['Lossless', 'Lossy'])
        self.png_compression_type_combobox.setCurrentText('Lossless')
        advanced_layout.addRow(self.png_compression_checkbox)
        advanced_layout.addRow("PNG Compression Type:", self.png_compression_type_combobox)
        self.advanced_group.setLayout(advanced_layout)
        layout.addWidget(self.advanced_group)
        self.start_button = QPushButton("Start Conversion")
        self.start_button.clicked.connect(self.start_conversion)
        layout.addWidget(self.start_button)
        self.setLayout(layout)
        self.setWindowTitle('Bulk DDS/PNG PNG/DDS')
        self.setGeometry(300, 300, 400, 500)

    def toggle_advanced_settings(self, state):
        self.advanced_group.setEnabled(state == Qt.Checked)

    def select_source_directory(self):
        directory = QFileDialog.getExistingDirectory(self, "Select Source Directory")
        if directory:
            self.source_dir_label.setText(f"Source Directory: {directory}")
    
    def select_output_directory(self):
        directory = QFileDialog.getExistingDirectory(self, "Select Output Directory")
        if directory:
            self.output_dir_label.setText(f"Output Directory: {directory}")

    def start_conversion(self):
        source_dir = self.source_dir_label.text().replace("Source Directory: ", "")
        output_dir = self.output_dir_label.text().replace("Output Directory: ", "")
        if "Select" in source_dir or "Select" in output_dir:
            QMessageBox.warning(self, "Input Error", "Please select the source and output directories.")
            return
        try:
            if self.dds_to_png_radio.isChecked():
                compression_type = 'lossy' if self.png_compression_checkbox.isChecked() and self.png_compression_type_combobox.currentText() == 'Lossy' else 'lossless'
                keep_alpha = True
                resize = (
                    (self.resize_width_spinbox.value(), self.resize_height_spinbox.value())
                    if self.resize_checkbox.isChecked() and self.resize_width_spinbox.value() > 0 and self.resize_height_spinbox.value() > 0
                    else None
                )
                brightness = self.brightness_spinbox.value() if self.brightness_checkbox.isChecked() else 0
                contrast = self.contrast_spinbox.value() if self.contrast_checkbox.isChecked() else 0
                saturation = self.saturation_spinbox.value() if self.saturation_checkbox.isChecked() else 1
                sharpening = self.sharpening_enabled_checkbox.isChecked() if self.sharpening_checkbox.isChecked() else False
                blurring = self.blurring_enabled_checkbox.isChecked() if self.blurring_checkbox.isChecked() else False
                convert_dds_to_png(
                    source_dir, output_dir, compression_type=compression_type, keep_alpha=keep_alpha,
                    resize=resize, brightness=brightness, contrast=contrast, saturation=saturation,
                    sharpening=sharpening, blurring=blurring
                )
                QMessageBox.information(self, "Success", "DDS to PNG conversion completed successfully!")
            elif self.png_to_dds_radio.isChecked():
                keep_alpha = True
                convert_png_to_dds(
                    source_dir, output_dir, keep_alpha=keep_alpha
                )
                QMessageBox.information(self, "Success", "PNG to DDS conversion completed successfully!")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"An error occurred: {str(e)}")

if __name__ == '__main__':
    app = QApplication(sys.argv)
    ex = ConverterApp()
    ex.show()
    sys.exit(app.exec_())
import os
import re
import json
import shutil
import uuid
import sys
from pathlib import Path

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QFileDialog,
    QTextEdit, QProgressBar, QMessageBox, QGroupBox
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal

UUID_REGEX = re.compile(r'([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})')

OLED_STYLE = """
QMainWindow, QWidget {
    background-color: #000000;
    color: #e4e4e7;
    font-family: 'Segoe UI', -apple-system, BlinkMacSystemFont, Roboto, sans-serif;
    font-size: 13px;
}

QGroupBox {
    border: 1px solid #1f1f23;
    border-radius: 8px;
    margin-top: 12px;
    padding-top: 14px;
    font-weight: 600;
    color: #a1a1aa;
}

QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 12px;
    padding: 0 4px;
}

QLabel {
    color: #a1a1aa;
    font-weight: 500;
}

QLineEdit {
    background-color: #09090b;
    border: 1px solid #27272a;
    border-radius: 6px;
    color: #fafafa;
    padding: 8px 12px;
}

QLineEdit:focus {
    border: 1px solid #10b981;
}

QPushButton {
    background-color: #121215;
    border: 1px solid #27272a;
    border-radius: 6px;
    color: #fafafa;
    padding: 8px 16px;
    font-weight: 500;
}

QPushButton:hover {
    background-color: #1f1f23;
    border-color: #3f3f46;
}

QPushButton:pressed {
    background-color: #09090b;
}

QPushButton#btn_action {
    background-color: #10b981;
    color: #000000;
    font-weight: 700;
    font-size: 14px;
    border: none;
    border-radius: 6px;
    height: 40px;
}

QPushButton#btn_action:hover {
    background-color: #059669;
}

QPushButton#btn_action:disabled {
    background-color: #18181b;
    color: #52525b;
}

QProgressBar {
    background-color: #09090b;
    border: 1px solid #1f1f23;
    border-radius: 6px;
    text-align: center;
    color: #e4e4e7;
    font-weight: 600;
    height: 18px;
}

QProgressBar::chunk {
    background-color: #10b981;
    border-radius: 5px;
}

QTextEdit {
    background-color: #030303;
    border: 1px solid #1f1f23;
    border-radius: 8px;
    color: #10b981;
    font-family: 'Consolas', 'Courier New', monospace;
    font-size: 12px;
    padding: 8px;
}

QScrollBar:vertical {
    background: #000000;
    width: 8px;
    margin: 0;
}

QScrollBar::handle:vertical {
    background: #27272a;
    min-height: 20px;
    border-radius: 4px;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}
"""

def clean_num(val):
    try:
        f = float(val)
        return int(f) if f.is_integer() else round(f, 6)
    except ValueError:
        return 0

def parse_mod_info(file_path):
    info = {}
    if not file_path.exists():
        return info
    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            line = line.strip()
            if "=" in line and not line.startswith(("#", ";")):
                k, v = line.split("=", 1)
                info[k.strip().lower()] = v.strip()
    return info

class ConversionWorker(QThread):
    progress = pyqtSignal(int, int)
    log = pyqtSignal(str)
    finished = pyqtSignal(bool, str)

    def __init__(self, source_dir, output_dir, blacklist_path):
        super().__init__()
        self.source_dir = Path(source_dir)
        self.output_dir = Path(output_dir)
        self.blacklist_path = Path(blacklist_path) if blacklist_path else None
        self.mod_folder_name = "pz3d"

    def run(self):
        try:
            self.log.emit("Starting migration...")

            # 1. Load door/stair blacklist
            blacklist = set()
            if self.blacklist_path and self.blacklist_path.exists():
                with open(self.blacklist_path, "r", encoding="utf-8", errors="ignore") as bf:
                    for line in bf:
                        line = line.strip().lower()
                        if line and not line.startswith(("#", "//", ";")):
                            blacklist.add(line)
                self.log.emit(f"Loaded {len(blacklist)} blacklisted door & stair sprites.")
            else:
                self.log.emit("[Warning] No blacklist file loaded. All sprites will be processed.")

            author_name = "Local artist"
            mod_info_files = list(self.source_dir.glob("**/mod.info"))
            if mod_info_files:
                parsed = parse_mod_info(mod_info_files[0])
                author_name = parsed.get("author", author_name)
                self.log.emit(f"Detected mod author: {author_name}")

            # 2. Copy Version Folders (e.g., 42.20.4/) and mod.info
            self.log.emit("Copying version folders & metadata...")
            for mi in mod_info_files:
                rel = mi.relative_to(self.source_dir)
                if len(rel.parts) > 1:
                    top_folder = rel.parts[0]
                    src_ver_dir = self.source_dir / top_folder
                    dest_ver_dir = self.output_dir / top_folder
                    if not dest_ver_dir.exists():
                        self.log.emit(f"Copied version folder: {top_folder}/")
                        shutil.copytree(src_ver_dir, dest_ver_dir, dirs_exist_ok=True)
                else:
                    self.output_dir.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(mi, self.output_dir / "mod.info")
                    self.log.emit("Copied root mod.info")

            for meta in ["poster.png", "icon.png"]:
                src_meta = self.source_dir / meta
                if src_meta.exists():
                    shutil.copy2(src_meta, self.output_dir / meta)

            # 3. Parse .properties manifests
            self.log.emit("Scanning for .properties manifests...")
            prop_files = list(self.source_dir.glob("**/*.properties"))

            if not prop_files:
                self.finished.emit(False, "No .properties manifests found in the selected Mod Directory.")
                return

            self.log.emit(f"Found {len(prop_files)} properties files.")

            models = {}
            bindings = {}
            skipped_doors_stairs = 0

            for pf in prop_files:
                with open(pf, "r", encoding="utf-8", errors="ignore") as f:
                    for line in f:
                        line = line.strip()
                        if not line or line.startswith(("#", ";")):
                            continue

                        if line.startswith("model."):
                            k, v = line.split("=", 1)
                            model_id = k[len("model."):].strip()
                            rel_path = v.strip()

                            full_path = (pf.parent / rel_path).resolve()
                            if not full_path.exists():
                                alt_path = (self.source_dir / rel_path).resolve()
                                if alt_path.exists():
                                    full_path = alt_path

                            models[model_id] = full_path

                        elif line.startswith("bind."):
                            k, v = line.split("=", 1)
                            tile_name = k[len("bind."):].strip()

                            # Filter out doors and stairs from blacklist
                            if tile_name.lower() in blacklist:
                                skipped_doors_stairs += 1
                                continue

                            parts = [p.strip() for p in v.split(",")]
                            if len(parts) >= 6:
                                model_id = parts[0]
                                rot_z = clean_num(parts[1])
                                raw_x = float(parts[2])
                                raw_y = float(parts[3])
                                raw_z = clean_num(parts[4])
                                scale = clean_num(parts[5])

                                # Hardcoded center offset: x + 0.5, y + 0.5
                                final_x = clean_num(raw_x + 0.5)
                                final_y = clean_num(raw_y + 0.5)

                                if model_id not in bindings:
                                    bindings[model_id] = []

                                bindings[model_id].append({
                                    "tile": tile_name,
                                    "placement": {
                                        "position": [final_x, final_y, raw_z],
                                        "rotation": [0, 0, rot_z],
                                        "scale": [scale, scale, scale]
                                    }
                                })

            self.log.emit(f"Skipped {skipped_doors_stairs} door and stair bindings.")
            self.log.emit(f"Loaded {sum(len(b) for b in bindings.values())} valid bindings across {len(models)} models.")

            # 4. Target directory: common/media/pz3d/assets
            target_assets_dir = self.output_dir / "common" / "media" / self.mod_folder_name / "assets"
            target_assets_dir.mkdir(parents=True, exist_ok=True)

            # 5. Group Models into Assets & Prune empty ones
            assets_dict = {}

            for model_id, obj_path in models.items():
                # If all bindings for this model were doors/stairs, skip it completely
                model_bindings = bindings.get(model_id, [])
                if not model_bindings:
                    continue

                match = UUID_REGEX.search(str(obj_path))
                if match:
                    asset_uuid = match.group(1).lower()
                else:
                    asset_uuid = str(uuid.uuid5(uuid.NAMESPACE_DNS, str(obj_path)))

                if asset_uuid not in assets_dict:
                    friendly_name = model_bindings[0]["tile"].replace("_", " ").title()

                    assets_dict[asset_uuid] = {
                        "directory": asset_uuid,
                        "id": asset_uuid,
                        "name": friendly_name,
                        "author": author_name,
                        "allowRepack": True,
                        "variants": {},
                        "source_dirs": set()
                    }

                variant_name = obj_path.stem or "default"
                assets_dict[asset_uuid]["variants"][variant_name] = {
                    "file": obj_path.name,
                    "bindings": model_bindings
                }

                if obj_path.exists():
                    assets_dict[asset_uuid]["source_dirs"].add(obj_path.parent)

            # 6. Copy 3D model files & textures (Only for active, non-door assets)
            total_assets = len(assets_dict)
            copied_files_count = 0
            final_assets_list = []

            for i, (asset_key, data) in enumerate(assets_dict.items(), start=1):
                self.progress.emit(i, total_assets)

                asset_subfolder = target_assets_dir / data["directory"]
                asset_subfolder.mkdir(parents=True, exist_ok=True)

                for s_dir in data["source_dirs"]:
                    for f in s_dir.iterdir():
                        if f.is_file() and f.suffix.lower() in [".obj", ".mtl", ".png", ".jpg"]:
                            dest = asset_subfolder / f.name
                            if not dest.exists():
                                shutil.copy2(f, dest)
                                copied_files_count += 1

                final_assets_list.append({
                    "directory": data["directory"],
                    "id": data["id"],
                    "name": data["name"],
                    "author": data["author"],
                    "allowRepack": data["allowRepack"],
                    "variants": data["variants"]
                })

            # 7. Save assets.json
            output_json = {
                "schema": "pz3d:assets/1",
                "assets": final_assets_list
            }

            json_path = target_assets_dir / "assets.json"
            self.log.emit(f"Writing {json_path}...")
            with open(json_path, "w", encoding="utf-8") as jf:
                json.dump(output_json, jf, indent=2)

            msg = (
                f"Conversion completed successfully!\n\n"
                f"- Excluded door/stair bindings: {skipped_doors_stairs}\n"
                f"- Clean Assets Migrated: {total_assets}\n"
                f"- Files Copied: {copied_files_count}\n"
                f"- Path: common/media/pz3d/assets/assets.json"
            )
            self.finished.emit(True, msg)

        except Exception as e:
            self.finished.emit(False, f"Error occurred: {str(e)}")


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PZ3D Schema Migrator")
        self.resize(680, 560)
        self.init_ui()

    def init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setSpacing(14)
        layout.setContentsMargins(18, 18, 18, 18)

        # Paths Group
        grp_paths = QGroupBox("Directories & Exclusion List")
        paths_layout = QVBoxLayout(grp_paths)
        paths_layout.setSpacing(10)

        # Mod Directory (Source)
        h1 = QHBoxLayout()
        self.txt_source = QLineEdit()
        self.txt_source.setPlaceholderText("Select the root mod folder...")
        btn_src = QPushButton("Browse...")
        btn_src.clicked.connect(self.browse_source)
        h1.addWidget(QLabel("Mod Directory:"))
        h1.addWidget(self.txt_source)
        h1.addWidget(btn_src)
        paths_layout.addLayout(h1)

        # Output Directory
        h2 = QHBoxLayout()
        self.txt_output = QLineEdit()
        self.txt_output.setPlaceholderText("Select destination folder...")
        btn_out = QPushButton("Browse...")
        btn_out.clicked.connect(self.browse_output)
        h2.addWidget(QLabel("Output Dir:"))
        h2.addWidget(self.txt_output)
        h2.addWidget(btn_out)
        paths_layout.addLayout(h2)

        # Blacklist File (doors_and_stairs.txt)
        h3 = QHBoxLayout()
        self.txt_blacklist = QLineEdit()
        self.txt_blacklist.setPlaceholderText("doors_and_stairs.txt (Auto-detected if present)")
        btn_bl = QPushButton("Browse...")
        btn_bl.clicked.connect(self.browse_blacklist)
        h3.addWidget(QLabel("Exclude List:"))
        h3.addWidget(self.txt_blacklist)
        h3.addWidget(btn_bl)
        paths_layout.addLayout(h3)

        # Auto-detect doors_and_stairs.txt in the current directory
        default_bl = Path("doors_and_stairs.txt")
        if default_bl.exists():
            self.txt_blacklist.setText(str(default_bl.resolve()))

        layout.addWidget(grp_paths)

        # Progress Bar
        self.pbar = QProgressBar()
        self.pbar.setValue(0)
        layout.addWidget(self.pbar)

        # Console / Logs
        self.txt_log = QTextEdit()
        self.txt_log.setReadOnly(True)
        layout.addWidget(self.txt_log)

        # Action Button
        self.btn_convert = QPushButton("Start Migration")
        self.btn_convert.setObjectName("btn_action")
        self.btn_convert.clicked.connect(self.start_conversion)
        layout.addWidget(self.btn_convert)

    def browse_source(self):
        d = QFileDialog.getExistingDirectory(self, "Select Mod Directory")
        if d:
            self.txt_source.setText(d)
            if not self.txt_output.text():
                self.txt_output.setText(d + "_migrated")

    def browse_output(self):
        d = QFileDialog.getExistingDirectory(self, "Select Output Directory")
        if d:
            self.txt_output.setText(d)

    def browse_blacklist(self):
        f, _ = QFileDialog.getOpenFileName(self, "Select doors_and_stairs.txt", "", "Text Files (*.txt);;All Files (*)")
        if f:
            self.txt_blacklist.setText(f)

    def append_log(self, text):
        self.txt_log.append(text)

    def update_progress(self, val, total):
        self.pbar.setMaximum(total)
        self.pbar.setValue(val)

    def start_conversion(self):
        src = self.txt_source.text().strip()
        out = self.txt_output.text().strip()
        bl = self.txt_blacklist.text().strip()

        if not src or not os.path.exists(src):
            QMessageBox.critical(self, "Error", "Please select a valid Mod Directory.")
            return

        if not out:
            QMessageBox.critical(self, "Error", "Please select a destination Output Directory.")
            return

        self.btn_convert.setEnabled(False)
        self.txt_log.clear()
        self.pbar.setValue(0)

        self.worker = ConversionWorker(src, out, bl)
        self.worker.log.connect(self.append_log)
        self.worker.progress.connect(self.update_progress)
        self.worker.finished.connect(self.on_finished)
        self.worker.start()

    def on_finished(self, success, message):
        self.btn_convert.setEnabled(True)
        if success:
            QMessageBox.information(self, "Done", message)
            self.append_log("\n--- FINISHED SUCCESSFULLY ---")
        else:
            QMessageBox.critical(self, "Failed", message)
            self.append_log(f"\n--- FAILED: {message} ---")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setStyleSheet(OLED_STYLE)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())

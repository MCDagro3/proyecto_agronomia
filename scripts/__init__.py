from scripts.config import ROOT, data_sources, data_folders
import os


DATA_DIR = ROOT / "data"
if not os.path.exists(DATA_DIR):
    os.mkdir(DATA_DIR)
    for folder in data_folders:
        os.mkdir(DATA_DIR / folder)
        for source in data_sources:
            os.mkdir(DATA_DIR / folder / source)

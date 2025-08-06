import os
import json
import faiss
import numpy as np
from sentence_transformers import SentenceTransformer

FILE_INDEX = "file_index.faiss"
FILE_METADATA = "file_metadata.jsonl"
UNDO_LOG_PATH = "undo_log.json"

model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")

def load_undo_map():
    if not os.path.exists(UNDO_LOG_PATH):
        return {}
    with open(UNDO_LOG_PATH) as f:
        entries = json.load(f)
        return {entry["to"]: entry["from"] for entry in entries}

def resolve_grouped_path(original_path, undo_map):
    current = original_path
    while current != "/":
        if current in undo_map:
            relative = os.path.relpath(original_path, current)
            return os.path.join(undo_map[current], relative)
        current = os.path.dirname(current)
    return original_path

def classify_text(content):
    if not content.strip():
        return "Uncategorized"

    vec = model.encode(content).astype("float32").reshape(1, -1)

    try:
        index = faiss.read_index(FILE_INDEX)
        with open(FILE_METADATA, "r") as f:
            metadata = [json.loads(line) for line in f]

        D, I = index.search(vec, 1)
        closest_file_path = metadata[I[0][0]]["path"]
        parent_folder = os.path.dirname(closest_file_path)

        undo_map = load_undo_map()
        resolved_path = resolve_grouped_path(parent_folder, undo_map)

        return resolved_path

    except Exception as e:
        print("⚠️ Failed to classify with embedding:", e)
        return "Uncategorized"

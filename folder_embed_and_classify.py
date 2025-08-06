import os, json, gc, hashlib
import numpy as np
import faiss
import torch
from tqdm import tqdm
from extractor import extract_text
from transformers import AutoTokenizer, AutoModel
import asyncio
from embedding_state import embedding_cancel_event






# --- Config ---
MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
EMBEDDING_DIM = 384
CHUNK_SIZE = 512
FLUSH_INTERVAL = 10

FOLDER_INDEX_FILE = "folder_index.faiss"
FOLDER_METADATA_FILE = "folder_metadata.jsonl"
FILE_INDEX_FILE = "file_index.faiss"
FILE_METADATA_FILE = "file_metadata.jsonl"

USE_MPS = torch.backends.mps.is_available()
DEVICE = torch.device("mps" if USE_MPS else "cpu")


# --- Model ---
tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
model = AutoModel.from_pretrained(MODEL_NAME).to(DEVICE)
model.eval()

# --- Helpers ---
def format_text(text, model_name):
    if "e5" in model_name:
        return f"passage: {text}"
    elif "bge" in model_name:
        return f"{text.strip()} </s>"
    return text

def clean_text(text):
    return ' '.join(text.split())

def hash_folder(path):
    h = hashlib.sha256()
    for dirpath, _, filenames in os.walk(path):
        for f in sorted(filenames):
            try:
                with open(os.path.join(dirpath, f), "rb") as file:
                    h.update(file.read(4096))
            except: continue
    return h.hexdigest()

def hash_file(path):
    h = hashlib.sha256()
    try:
        with open(path, "rb") as f:
            while chunk := f.read(4096):
                h.update(chunk)
    except: pass
    return h.hexdigest()

def embed_text(text):
    chunks = [text[i:i+CHUNK_SIZE] for i in range(0, len(text), CHUNK_SIZE)]
    embeddings = []

    for chunk in chunks:
        if embedding_cancel_event.is_set():
            print("⛔ Cancel detected inside embed_text")
            return None
        formatted = format_text(clean_text(chunk), MODEL_NAME)
        inputs = tokenizer(formatted, return_tensors="pt", truncation=True, max_length=512).to(DEVICE)
        with torch.no_grad():
            outputs = model(**inputs)
            emb = outputs.last_hidden_state[:, 0]
            emb = torch.nn.functional.normalize(emb, p=2, dim=1)
            embeddings.append(emb.cpu().numpy())

    return np.mean(np.vstack(embeddings), axis=0).astype("float32")

def load_cache(file):
    if not os.path.exists(file): return {}
    with open(file, "r") as f:
        return {json.loads(line)["path"]: json.loads(line) for line in f}

def save_jsonl(entries, path):
    with open(path, "w") as f:
        for e in entries:
            f.write(json.dumps(e) + "\n")

async def embed_folders_and_files(root_dir, progress_callback=None,broadcast_callback=None):
    file_count = 0
    folder_cache = load_cache(FOLDER_METADATA_FILE)
    file_cache = load_cache(FILE_METADATA_FILE)

    folders = [f for f in os.listdir(root_dir) if os.path.isdir(os.path.join(root_dir, f))]
    folder_index = faiss.IndexFlatL2(EMBEDDING_DIM)
    file_index = faiss.IndexFlatL2(EMBEDDING_DIM)

    folder_metadata = []
    file_metadata = []

    total_folders = len(folders)
    done_folders = 0

    print(f"📁 Embedding folders & files in {root_dir}...")

    for folder in folders:
        if embedding_cancel_event.is_set():
            print("⛔ Embedding was cancelled. Skipping final save.")
            if progress_callback:
                await progress_callback(done_folders, total_folders)

            if broadcast_callback:
                await broadcast_callback({"action": "embed_stopped"})
            return



        folder_path = os.path.join(root_dir, folder)
        folder_hash = hash_folder(folder_path)

        if folder_path in folder_cache and folder_cache[folder_path]["hash"] == folder_hash:
            # ✅ Cached folder
            vec = np.array(folder_cache[folder_path]["embedding"], dtype="float32")
            folder_index.add(np.array([vec]))
            folder_metadata.append(folder_cache[folder_path])
            print(f"📝 Folder is already embedded: {folder}")
        else:
            # 🆕 Needs embedding
            text = ""
            for dirpath, _, files in os.walk(folder_path):
                for f in files:
                    if embedding_cancel_event.is_set():
                        print("⛔ Embedding was cancelled during file loop.")
                        if progress_callback:
                            await progress_callback(done_folders, total_folders)
                        if broadcast_callback:
                            await broadcast_callback({"action": "embed_stopped"})
                        return
                    text += extract_text(os.path.join(dirpath, f)) + "\n"

            if not text.strip():
                print(f"⚠️ Skipped empty folder: {folder}")
            else:
                emb = embed_text(text)
                folder_index.add(np.array([emb], dtype="float32"))
                entry = {
                    "folder": folder, "path": folder_path,
                    "embedding": emb.tolist(), "hash": folder_hash
                }
                folder_metadata.append(entry)
                faiss.write_index(folder_index, FOLDER_INDEX_FILE)
                save_jsonl(folder_metadata, FOLDER_METADATA_FILE)
                print(f"📝 Embedded folder: {folder}")

        # 🔁 Embed individual files in this folder
        for dirpath, _, files in os.walk(folder_path):
            for f in files:
                if embedding_cancel_event.is_set():
                    print("⛔ Embedding was cancelled during file loop.")
                    if progress_callback:
                        await progress_callback(done_folders, total_folders)
                    if broadcast_callback:
                         await broadcast_callback({"action": "embed_stopped"})
                    return

                fpath = os.path.join(dirpath, f)
                fhash = hash_file(fpath)

                if fpath in file_cache and file_cache[fpath]["hash"] == fhash:
                    vec = np.array(file_cache[fpath]["embedding"], dtype="float32")
                    file_index.add(np.array([vec]))
                    file_metadata.append(file_cache[fpath])
                    continue

                text = extract_text(fpath)
                if not text.strip(): continue

                try:
                    emb = embed_text(text)
                    file_index.add(np.array([emb], dtype="float32"))
                    entry = {
                        "file": f, "path": fpath,
                        "root_folder": folder_path,
                        "embedding": emb.tolist(),
                        "hash": fhash
                    }
                    file_metadata.append(entry)
                    print(f"📄 Embedded file: {f}")
                    file_count += 1

                    if file_count % FLUSH_INTERVAL == 0:
                        save_jsonl(file_metadata, FILE_METADATA_FILE)
                        faiss.write_index(file_index, FILE_INDEX_FILE)
                        print(f"💾 Flushed file cache at {len(file_metadata)} files")
                        file_count = 0

                except Exception as e:
                    print(f"❌ File embedding failed: {f} — {e}")
                gc.collect()

        done_folders += 1
        if progress_callback:
            await progress_callback(done_folders, total_folders)

    # Final save
    faiss.write_index(folder_index, FOLDER_INDEX_FILE)
    faiss.write_index(file_index, FILE_INDEX_FILE)
    save_jsonl(folder_metadata, FOLDER_METADATA_FILE)
    save_jsonl(file_metadata, FILE_METADATA_FILE)

    print(f"✅ Done! Indexed {len(folder_metadata)} folders, {len(file_metadata)} files.")
    if progress_callback:
        await progress_callback(total_folders, total_folders)

if __name__ == "__main__":
    root_dir = os.path.expanduser("~/Desktop")
    print(f"🚀 Starting embedding in: {root_dir}")
    embed_folders_and_files(root_dir)

import os
import json
import faiss
import numpy as np
from sklearn.cluster import KMeans

UNDO_LOG_PATH = os.path.expanduser("~/Desktop/grouping_undo_log.json")
FAISS_INDEX_PATH = "./folder_index.faiss"
METADATA_PATH = "./folder_metadata.jsonl"


def build_prompt_from_folders(folder_names):
    folder_list = "\n".join(f"- {name}" for name in folder_names)
    prompt = f"""### Task:
You are an assistant specialized in categorizing folders. Given a list of folder names, choose a **short, specific**, and **category-representative** group name (2–4 words max). 
Only use words or concepts **directly inferred** from the names. Avoid generic words like "Group", "Collection", "Misc", "Mixed", or "Various".

### Folder Names:
{folder_list}

### Output:
Group Name:"""
    return prompt


def get_llm_group_name(llm, folder_names):
    prompt = build_prompt_from_folders(folder_names)
    try:
        response = llm(prompt, max_tokens=20, stop=["\n"])
        name = response["choices"][0]["text"].strip()
        return name.replace(" ", "_").replace("-", "_") if name else None
    except Exception as e:
        print(f"Error generating group name: {e}")
        return None


async def group_folders_from_faiss(k=4, llm=None, progress_callback=None):
    # Load FAISS index
    index = faiss.read_index(FAISS_INDEX_PATH)

    # Load metadata
    folder_paths = []
    with open(METADATA_PATH, "r") as f:
        for line in f:
            obj = json.loads(line)
            folder_paths.append(obj["path"])

    # Get embeddings
    embeddings = index.reconstruct_n(0, index.ntotal)
    embeddings = np.array(embeddings)

    total = len(folder_paths)
    if progress_callback:
        await progress_callback(0, total)

    for i in range(total):
        if progress_callback:
            await progress_callback(i + 1, total)

    # Cluster embeddings
    kmeans = KMeans(n_clusters=k, random_state=42, n_init="auto")
    labels = kmeans.fit_predict(embeddings)

    # Group folder paths
    groups = [[] for _ in range(k)]
    for path, label in zip(folder_paths, labels):
        groups[label].append(path)

    desktop = os.path.expanduser("~/Desktop")
    undo_log = []
    group_name_map = {}

    for i, group in enumerate(groups):
        folder_names = [os.path.basename(p) for p in group]
        group_name = get_llm_group_name(llm, folder_names) if llm else f"Group_{i}"
        print(f"Group {i + 1}: {folder_names} → Suggested name: {group_name}")
        group_name = group_name or f"Group_{i}"

        group_dir = os.path.join(desktop, group_name)
        os.makedirs(group_dir, exist_ok=True)
        group_name_map[group_name] = folder_names

        for folder_path in group:
            if not os.path.exists(folder_path):
                print(f"Folder does not exist: {folder_path}")
                continue

            folder_name = os.path.basename(folder_path)
            new_path = os.path.join(group_dir, folder_name)

            try:
                os.rename(folder_path, new_path)
                undo_log.append({"from": new_path, "to": folder_path})
            except Exception as e:
                print(f"Failed to move {folder_path}: {e}")

    # Save undo log
    with open(UNDO_LOG_PATH, "w") as f:
        json.dump(undo_log, f, indent=2)

    # Indicate completion
    yield {"final": True, "groups": group_name_map}


async def undo_grouping(progress_callback=None):
    if not os.path.exists(UNDO_LOG_PATH):
        print("Undo log not found.")
        return {"status": "error", "message": "Undo log not found."}

    with open(UNDO_LOG_PATH, "r") as f:
        undo_moves = json.load(f)

    errors = []
    total = len(undo_moves)

    for i, move in enumerate(undo_moves):
        src = move["from"]
        dst = move["to"]

        print(f"Moving back: {src} → {dst}")
        if not os.path.exists(src):
            print(f"Source not found: {src}")
            errors.append(f"Source missing: {src}")
            continue

        if os.path.exists(dst):
            print(f"Destination exists, skipping: {dst}")
            errors.append(f"Destination exists: {dst}")
            continue

        try:
            os.rename(src, dst)
        except Exception as e:
            print(f"Rename failed: {e}")
            errors.append(str(e))

        if progress_callback:
            await progress_callback(i + 1, total)

    if not errors:
        os.remove(UNDO_LOG_PATH)
        return {"status": "success", "message": "Undo completed successfully."}
    else:
        return {
            "status": "partial",
            "message": "Some items could not be undone.",
            "errors": errors
        }

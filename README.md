# Smart File Organizer

Smart File Organizer is an AI-powered desktop application that automatically organizes files in real time.  
It uses embeddings, clustering (FAISS), and LLM-generated folder names to create a meaningful folder structure without manual effort.  

Built with:  
- Electron (frontend GUI)  
- Python (backend WebSocket server)  
- FAISS + LLMs (AI-powered grouping and folder naming)  
- SQLite (logging and history tracking)  

---

## Features  

- Real-time file monitoring with OS event detection  
- AI embeddings for semantic file representation  
- FAISS-based clustering and LLM-generated folder names  
- Undo and history tracking with SQLite  
- Live progress display and cancellation option for embeddings  

---

## Getting Started  

### Prerequisites  
- Node.js and npm  
- Python 3.9+  
- FAISS and other Python dependencies  

### Installation  

```bash
# Clone the repo
git clone https://github.com/rupesh-mr/smart_file_organiser
cd smart-file-organizer

# Install backend dependencies
pip install -r requirements.txt

# Install frontend dependencies
cd gui
npm install
```

---

### Running the App  

1. Start the backend (Python server):  
   ```bash
   python main.py
   ```

2. Start the frontend (Electron app):  
   ```bash
   cd gui
   npm start
   ```

---

## Models

This project requires a local LLM model file in the `models/` directory.  
By default, we use **Phi-2 (quantized, GGUF format)**.

### Setup

Create a `models/` folder if it doesn't exist:

```bash
mkdir -p models
```

Download the model using the provided script:

```bash
./download_model.sh
```

Alternatively, download manually:

```bash
cd models
wget https://huggingface.co/TheBloke/phi-2-GGUF/resolve/main/phi-2.Q2_K.gguf
```

Once downloaded, the file structure should look like:

```
models/
└── phi-2.Q2_K.gguf
```

The application will automatically detect and load this model at runtime.

---

## Project Structure  

```
smart-file-organizer/
│
├── gui/                      # Electron + frontend code
├── models/                   # Model files (ignored in git)
├── venv/                     # Python virtual environment (ignored in repo)
│
├── classifier.py              # File type classifier
├── embedding_state.py         # Embedding state management
├── extractor.py               # File content extractor
├── folder_embed_and_classify.py
├── group_folders_faiss.py     # FAISS clustering logic
├── logger.py                  # Logging utility
├── main.py                    # Backend entry point
├── shared_llm.py              # Shared LLM interface
├── socket_server.py           # WebSocket server
│
├── file_index.faiss           # FAISS index for files
├── folder_index.faiss         # FAISS index for folders
├── file_metadata.jsonl        # File metadata storage
├── folder_metadata.jsonl      # Folder metadata storage
├── file_logs.db               # SQLite database for logs/history
│
└── README.md
```

---

## Usage Flow  

1. For new users, click **Start Embedding** after launching the app.  
   - This generates embeddings for your files.  
2. Add files to the watch folder — they appear instantly in the app.  
3. Click **Group Files** to cluster files and assign AI-generated folder names.  
4. Use **Undo** to revert or **History** to review past operations.  
 
---

## License  

This project is licensed under the MIT License.  

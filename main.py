import time
import os
import shutil
import asyncio
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from extractor import extract_text
from classifier import classify_text
from socket_server import start_socket_server, broadcast
from logger import init_db, log_file
from shared_llm import llm

DOWNLOADS_FOLDER = os.path.expanduser("~/Downloads")


def summarize_with_llm(text, filename=""):
    if not text.strip():
        print("No usable text extracted from file.")
        return "File content is empty or unreadable."

    ext = os.path.splitext(filename)[1].lower()

    if ext == ".py":
        instruction = "Summarize what this Python script does, including main functions and purpose."
    elif ext == ".md":
        instruction = "Summarize this Markdown document. Extract the purpose and key points."
    elif ext in [".pdf", ".docx", ".txt"]:
        instruction = "Summarize this document, highlighting the main ideas or topics covered."
    else:
        instruction = "Summarize the content below in a concise manner."

    prompt = f"""### Instruction:
{instruction}

### Input:
{text[:2000]}

### Summary:"""

    print("Prompt preview:", prompt[:300])

    try:
        output = llm(prompt, max_tokens=200, stop=["###"])
        summary = output["choices"][0]["text"].strip()

        if not summary:
            print("LLM returned an empty summary.")
            return "Summary was empty."

        return summary

    except Exception as e:
        print("LLM error:", e)
        return "LLM summarization failed."


class FileHandler(FileSystemEventHandler):
    def __init__(self, loop):
        self.loop = loop

    def on_created(self, event):
        print(f"[FileWatcher] New file created: {event.src_path}")
        if not event.is_directory:
            filename = os.path.basename(event.src_path)
            ext = os.path.splitext(filename)[1].lower()

            if filename.startswith('.') or ext in ('.crdownload', '.part', ''):
                return

            time.sleep(1)  # wait for file write to finish

            content = extract_text(event.src_path)
            category = classify_text(content)

            try:
                summary = summarize_with_llm(content, filename)
            except Exception as e:
                print("LLM summarization failed, fallback:", e)
                summary = content.strip().replace('\n', ' ')[:300] + "..."

            log_file(
                filename=filename,
                path=event.src_path,
                filetype=ext,
                category=category,
                summary=summary
            )

            print(f"[Broadcast] {filename} → {category}")

            asyncio.run_coroutine_threadsafe(
                broadcast({
                    "filename": filename,
                    "category": category,
                    "path": event.src_path,
                    "summary": summary
                }),
                self.loop
            )

            target_folder = os.path.join(DOWNLOADS_FOLDER, category)
            os.makedirs(target_folder, exist_ok=True)
            # Optional: move file to categorized folder


async def main():
    init_db()
    await start_socket_server()
    print("WebSocket server started")

    loop = asyncio.get_running_loop()

    observer = Observer()
    handler = FileHandler(loop)
    observer.schedule(handler, path=DOWNLOADS_FOLDER, recursive=False)
    observer.start()

    try:
        await asyncio.Future()
    except KeyboardInterrupt:
        observer.stop()
    observer.join()


if __name__ == "__main__":
    asyncio.run(main())

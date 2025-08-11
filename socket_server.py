import asyncio
import websockets
import json
import os
import shutil
from group_folders_faiss import group_folders_from_faiss, undo_grouping
from shared_llm import llm
from folder_embed_and_classify import embed_folders_and_files
from embedding_state import embedding_cancel_event

connected_clients = set()
embedding_task = None  # Global handle to the current embedding task

async def handler(websocket):
    global embedding_task
    connected_clients.add(websocket)
    try:
        async for message in websocket:
            data = json.loads(message)
            action = data.get("action")

            if action == "group_folders":
                print("Received group_folders request")
                try:
                    async for update in group_folders_from_faiss(4, llm, progress_callback=send_progress):
                        if update.get("final"):
                            await websocket.send(json.dumps({
                                "action": "group_result",
                                "status": "success",
                                "groups": update["groups"]
                            }))
                except Exception as e:
                    await websocket.send(json.dumps({
                        "action": "group_result",
                        "status": "error",
                        "message": str(e)
                    }))
                continue

            response = {"action": "status", "status": "", "path": data.get("path")}

            if action == "move":
                src = data["path"]
                category = data["category"]
                filename = os.path.basename(src)
                target_folder = os.path.join(os.path.expanduser("~/Desktop"), category)
                os.makedirs(target_folder, exist_ok=True)
                dst = os.path.join(target_folder, filename)
                try:
                    shutil.move(src, dst)
                    response["status"] = "moved"
                except Exception as e:
                    print(f"Move failed: {e}")
                    response["status"] = "error"

            elif action == "skip":
                response["status"] = "skipped"

            elif action == "undo_grouping":
                try:
                    await websocket.send(json.dumps({
                        "action": "undo_result",
                        "status": "started"
                    }))
                except:
                    pass

                try:
                    await undo_grouping()
                    await websocket.send(json.dumps({
                        "action": "undo_result",
                        "status": "success"
                    }))
                except Exception as e:
                    await websocket.send(json.dumps({
                        "action": "undo_result",
                        "status": "error",
                        "message": str(e)
                    }))
                continue

            elif action == "start_embedding":
                print("Start embedding received")
                if embedding_task and not embedding_task.done():
                    await websocket.send(json.dumps({"action": "embed_already_running"}))
                    continue

                try:
                    embedding_cancel_event.clear()
                except Exception:
                    pass

                embedding_task = asyncio.create_task(
                    embed_folders_and_files(
                        os.path.expanduser("~/Desktop"),
                        progress_callback=send_progress,
                        broadcast_callback=broadcast
                    )
                )

                asyncio.create_task(wait_for_embedding_completion(websocket))
                await websocket.send(json.dumps({"action": "embed_started"}))
                continue

            elif action == "stop_embedding":
                print("stop_embedding received")
                try:
                    embedding_cancel_event.set()
                except Exception:
                    pass

                if embedding_task and not embedding_task.done():
                    embedding_task.cancel()
                    await websocket.send(json.dumps({"action": "embed_stopping"}))
                else:
                    await websocket.send(json.dumps({"action": "embed_not_running"}))
                continue

            await websocket.send(json.dumps(response))

    except websockets.exceptions.ConnectionClosed:
        print("Client disconnected")
    finally:
        connected_clients.discard(websocket)

async def wait_for_embedding_completion(websocket):
    global embedding_task
    try:
        await embedding_task
        try:
            await websocket.send(json.dumps({"action": "embed_complete", "status": "success"}))
        except Exception:
            pass
    except asyncio.CancelledError:
        print("Embedding task cancelled")
        try:
            await websocket.send(json.dumps({"action": "embed_stopped"}))
        except Exception:
            pass
    except Exception as e:
        print(f"Embedding task error: {e}")
        try:
            await websocket.send(json.dumps({
                "action": "embed_complete",
                "status": "error",
                "message": str(e)
            }))
        except Exception:
            pass
    finally:
        embedding_task = None

async def send_progress(done, total):
    if connected_clients:
        msg = json.dumps({
            "action": "embed_progress",
            "done": done,
            "total": total
        })
        await asyncio.gather(*(client.send(msg) for client in connected_clients), return_exceptions=True)

async def broadcast(file_info):
    if connected_clients:
        msg = json.dumps(file_info)
        await asyncio.gather(*(client.send(msg) for client in connected_clients), return_exceptions=True)

def start_socket_server():
    return websockets.serve(handler, "localhost", 8765)

if __name__ == "__main__":
    print("Starting socket server on ws://localhost:8765")
    loop = asyncio.get_event_loop()
    loop.run_until_complete(start_socket_server())
    loop.run_forever()

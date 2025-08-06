# import asyncio
# import websockets
# import json
# import os
# import shutil
# from group_folders_faiss import group_folders_from_faiss, undo_grouping
# from shared_llm import llm

# connected_clients = set()

# async def handler(websocket):
#     connected_clients.add(websocket)
#     try:
#         async for message in websocket:
#             data = json.loads(message)

#             if data.get("action") == "group_folders":
#                 print("📂 Received group_folders request")
#                 try:
#                     groups = group_folders_from_faiss(4,llm)
#                     await websocket.send(json.dumps({
#                         "action": "group_result",
#                         "status": "success",
#                         "groups": groups
#                     }))
#                 except Exception as e:
#                     print("❌ Grouping failed:", e)
#                     await websocket.send(json.dumps({
#                         "action": "group_result",
#                         "status": "error",
#                         "message": str(e)
#                     }))
#                 continue

#             response = {"action": "status", "status": "", "path": data.get("path")}

#             if data.get("action") == "move":
#                 src = data["path"]
#                 category = data["category"]
#                 filename = os.path.basename(src)
#                 target_folder = os.path.join(os.path.expanduser("~/Desktop"), category)
#                 os.makedirs(target_folder, exist_ok=True)
#                 dst = os.path.join(target_folder, filename)

#                 try:
#                     shutil.move(src, dst)
#                     print(f"✅ Moved {filename} to {target_folder}")
#                     response["status"] = "moved"
#                 except Exception as e:
#                     print(f"❌ Move failed: {e}")
#                     response["status"] = "error"

#             elif data.get("action") == "skip":
#                 print(f"⏭️ Skipped file: {data['path']}")
#                 response["status"] = "skipped"
            
#             elif data.get("action") == "undo_grouping":
#                 print("↩️ Undo grouping requested")
#                 result = undo_grouping()
#                 await websocket.send(json.dumps({
#                     "action": "undo_result",
#                     **result
#                 }))
            


#             # Send back status update
#             await websocket.send(json.dumps(response))

#     finally:
#         connected_clients.remove(websocket)
#         print("Client disconnected")

# async def broadcast(file_info):
#     print(f"[➡️ Sending to GUI] {file_info}")
#     print(f"[👥 Clients connected: {len(connected_clients)}]")

#     if connected_clients:
#         message = json.dumps(file_info)
#         await asyncio.gather(*(client.send(message) for client in connected_clients))

# def start_socket_server():
#     return websockets.serve(handler, "localhost", 8765)

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




async def handler(websocket):
    connected_clients.add(websocket)
    try:
        async for message in websocket:
            data = json.loads(message)

            if data.get("action") == "group_folders":
                print("📂 Received group_folders request")

                try:
                    # Step 1: Track progress from generator
                    async for update in group_folders_from_faiss(4, llm, progress_callback=send_progress):
                        if update.get("final"):
                            await websocket.send(json.dumps({
                                "action": "group_result",
                                "status": "success",
                                "groups": update["groups"]
                            }))
                except Exception as e:
                    print("❌ Grouping failed:", e)
                    await websocket.send(json.dumps({
                        "action": "group_result",
                        "status": "error",
                        "message": str(e)
                    }))
                continue

            response = {"action": "status", "status": "", "path": data.get("path")}

            if data.get("action") == "move":
                src = data["path"]
                category = data["category"]
                filename = os.path.basename(src)
                target_folder = os.path.join(os.path.expanduser("~/Desktop"), category)
                os.makedirs(target_folder, exist_ok=True)
                dst = os.path.join(target_folder, filename)

                try:
                    shutil.move(src, dst)
                    print(f"✅ Moved {filename} to {target_folder}")
                    response["status"] = "moved"
                except Exception as e:
                    print(f"❌ Move failed: {e}")
                    response["status"] = "error"

            elif data.get("action") == "skip":
                print(f"⏭️ Skipped file: {data['path']}")
                response["status"] = "skipped"

            elif data.get("action") == "undo_grouping":
                print("↩️ Undo grouping requested")
                
                async def progress_cb(done, total):
                    await websocket.send(json.dumps({
                        "action": "undo_progress",
                        "done": done,
                        "total": total
                    }))

                result = await undo_grouping(progress_callback=progress_cb)
                await websocket.send(json.dumps({
                    "action": "undo_result",
                    **result
                }))
            elif data.get("action") == "start_embedding":
                print("🧠 Start embedding received")
                embedding_cancel_event.clear()
                try:
                    await embed_folders_and_files(
                        os.path.expanduser("~/Desktop"),
                        progress_callback=send_progress,
                        broadcast_callback=broadcast
                    )
                    await websocket.send(json.dumps({"action": "embedding_complete", "status": "success"}))
                except asyncio.CancelledError:
                    await websocket.send(json.dumps({
                        "action": "embed_stopped"
                    }))
                continue  # 👈 prevent status fallback

            elif data["action"] == "stop_embedding":
                print("⛔ stop_embedding received")
                embedding_cancel_event.set()
                await websocket.send(json.dumps({"action": "embed_stopped"}))
                continue  # 👈 prevent fallback



            await websocket.send(json.dumps(response))

    finally:
        connected_clients.remove(websocket)
        print("❌ Client disconnected")

async def send_progress(done, total):
    if connected_clients:
        progress_data = {
            "action": "embed_progress",
            "done": done,
            "total": total
        }
        await asyncio.gather(*(client.send(json.dumps(progress_data)) for client in connected_clients))


async def broadcast(file_info):
    print(f"[➡️ Sending to GUI] {file_info}")
    print(f"[👥 Clients connected: {len(connected_clients)}]")

    if connected_clients:
        message = json.dumps(file_info)
        await asyncio.gather(*(client.send(message) for client in connected_clients))
def start_socket_server():
    return websockets.serve(handler, "localhost", 8765)

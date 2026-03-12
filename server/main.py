from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from server.connection_manager import ConnManager
import json, asyncio

# uvicorn server.main:app --reload --port 8000
# ngrok http --url=unwhite-lovetta-oozy.ngrok-free.dev 8000

app = FastAPI()
cm = ConnManager()

@app.websocket("/ws/{username}")
async def websocket_endpoint(websocket: WebSocket, username: str):
    await websocket.accept()

    await cm.connect(username, websocket)
    print(f"{username} connected")

    try:
        while True:
            raw_data = await websocket.receive_text()
            data = json.loads(raw_data)
            
            await cm.send_message(websocket, data)
    
    except WebSocketDisconnect:
        await cm.disconnect(username)
        print(f"{username} disconnected!")
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from server.connection_manager import ConnManager
import json, asyncio

# uvicorn server.main:app --reload --port 8000
# ngrok http --url=unwhite-lovetta-oozy.ngrok-free.dev 8000
# https://unwhite-lovetta-oozy.ngrok-free.dev

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
            
            if(data["type"] == "message"):
                await cm.send_message(websocket, data)

            if(data["type"] == "register_keys" or data["type"] == "request_keys"):
                await cm.handle_keys(websocket, data)

            if(data["type"] == "register" or data["type"] == "login"):
                await cm.handle_account(websocket, data)
    
    except WebSocketDisconnect:
        await cm.disconnect(username)
        print(f"{username} disconnected!")
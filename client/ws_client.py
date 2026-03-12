import websockets
import json

class WS_Client:
    def __init__(self): # server_url as a parameter later maybe
        # self.server_url = server_url
        # self.websocket = None # No connection yet
        self = self

    async def client_connect(self, account):
        base_path = "ws://localhost:8000/ws/"
        path = base_path + account
        self.websocket = await websockets.connect(path, ping_interval=30, ping_timeout=120)
        
        print(f"Connected as {account}")
        # async with websockets.connect(path) as ws:
        #     await ws.send("hello server")
        #     response = await ws.recv()
        #     print(response)

    async def send_message(self, data):
        await self.websocket.send(json.dumps(data))

    async def receive_message(self):
        response = await self.websocket.recv()
        return response
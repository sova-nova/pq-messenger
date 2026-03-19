from fastapi import FastAPI, WebSocket, WebSocketDisconnect
import json

class ConnManager:
    def __init__(self):
        self.dict = {}
        self.message_queue = {}
        self.key_storage = {}

    # When a user connects to the server, they are placed in the active dictionary
    async def connect(self, user, websocket):
        self.dict[user] = websocket

        # Check for queued messages
        if user in self.message_queue:
            for msg in self.message_queue[user]:
                await websocket.send_text(json.dumps(msg))
            
            count = len(self.message_queue[user])
            print(f"Delivered {count} queued messages to {user}")
            del self.message_queue[user]

    # WHen a user disconnects from the server, they are removed from the dictionary
    async def disconnect(self, user):
        self.dict.pop(user)

    #Check if a user is online for receiving
    def is_online(self, user):
        return user in self.dict
    
    def register_keys(self, user, public_kem, public_dsa):
        self.key_storage[user] = {
            "type": "request_keys",
            "public_kem": public_kem,
            "public_dsa": public_dsa
        }

    def get_keys(self, user):
        if user in self.key_storage:
            return self.key_storage[user]
        return None

    async def handle_keys(self, sender_ws, data):
        if(data["type"] == "register_keys"):
            user = data["user"]
            public_kem = data["public_kem"]
            public_dsa = data["public_dsa"]
            self.register_keys(user, public_kem, public_dsa)
            # print(self.get_keys(user)) # See if the keys are actually stored
        elif(data["type"] == "request_keys"):
            user = data["user"]
            key_data = self.get_keys(user)
            if key_data:
                response = {
                    "type": "request_keys",
                    "user": user,
                    "public_kem": key_data["public_kem"],
                    "public_dsa": key_data["public_dsa"]
                }
                await sender_ws.send_text(json.dumps(response))
                print(f"Keys sent for {user}")
            else:
                status = {"type": "status", "message": f"No keys found for {user}"}
                await sender_ws.send_text(json.dumps(status))

    async def send_message(self, sender_ws, data): # Sender_ws is for sending status back to the sender
        recipient = data["recipient"]
        if(self.is_online(recipient)):
            data["type"] = "message"
            await self.dict[recipient].send_text(json.dumps(data))
            # status = {"type": "status", "message": "Message sent!"}
            # await sender_ws.send_text(json.dumps(status))
        else:
            # Queue the message
            data["type"] = "message"
            if recipient not in self.message_queue:
                self.message_queue[recipient] = []
            self.message_queue[recipient].append(data)

            count = len(self.message_queue[recipient])
            # status = {
            #     "type": "status", 
            #     "message": f"{recipient} is offline. Message queued ({count} pending)."
            # }
            # await sender_ws.send_text(json.dumps(status))
            print(f"Queued message for {recipient}")

    
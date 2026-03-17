from fastapi import FastAPI, WebSocket, WebSocketDisconnect
import json

class ConnManager:
    def __init__(self):
        self.dict = {}
        self.message_queue = {}

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

    
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
import json

class ConnManager:
    def __init__(self):
        self.dict = {}

    # When a user connects to the server, they are placed in the active dictionary
    async def connect(self, user, websocket):
        self.dict.update({user: websocket})

    # WHen a user disconnects from the server, they are removed from the dictionary
    async def disconnect(self, user):
        self.dict.pop(user)

    #Check if a user is online for receiving
    def is_online(self, user):
        return user in self.dict

    async def send_message(self, sender_ws, data):
        recipient = data["recipient"]
        if(self.is_online(recipient)):
            data["type"] = "message"
            await self.dict[recipient].send_text(json.dumps(data))
            status = {"type": "status", "message": "Message sent!"}
            await sender_ws.send_text(json.dumps(status))
        else:
            status = {"type": "status", "message": "You recipient does not exist!"}
            await sender_ws.send_text(json.dumps(status))
            print("User does not exist!")

    
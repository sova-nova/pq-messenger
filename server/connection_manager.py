
from server.database import Database
import json
from argon2 import PasswordHasher

class ConnManager:
    def __init__(self):
        self.dict = {}
        self.key_storage = {}
        self.authenticated = set()
        self.ph = PasswordHasher()
        self.db = Database()

    # When a user connects to the server, they are placed in the active dictionary
    async def connect(self, user, websocket):
        self.dict[user] = websocket

        # # Deliver queued messages (from database)
        # queued = self.db.get_queued_messages(user)
        # if queued:
        #     for msg_id, msg_data in queued:
        #         await websocket.send_text(msg_data)
        #     print(f"Delivered {len(queued)} queued messages to {user}")
        #     self.db.delete_queued_messages(user)

    # When a user disconnects from the server, they are removed from the dictionary and authenticated set
    async def disconnect(self, user):
        if user in self.dict:
            del self.dict[user]
        self.authenticated.discard(user)    # ← remove auth on disconnect

    def is_authenticated(self, user):
        return user in self.authenticated
    
    def register_user(self, username, password):
        hashed = self.ph.hash(password)
        success = self.db.register_user(username, hashed)
        if success:
            self.authenticated.add(username)
        return success

    def login_user(self, username, password):
        stored_hash = self.db.get_password_hash(username)
        if not stored_hash:
            return False
        try:
            self.ph.verify(stored_hash, password)
            self.authenticated.add(username)
            return True
        except Exception:
            return False

    # Check if a user is online for receiving
    def is_online(self, user):
        return user in self.dict
    
    def register_keys(self, user, public_kem, public_dsa):
        # Cache in memory
        self.key_storage[user] = {
            "public_kem": public_kem,
            "public_dsa": public_dsa
        }
        # Save to database
        self.db.store_keys(user, public_kem, public_dsa)

    def get_keys(self, user):
        # Check memory cache first
        if user in self.key_storage:
            return self.key_storage[user]
        # Fall back to database
        keys = self.db.get_keys(user)
        if keys:
            self.key_storage[user] = keys
        return keys

    async def handle_keys(self, sender_ws, data):
        if(data["type"] == "register_keys"):
            user = data["user"]
            public_kem = data["public_kem"]
            public_dsa = data["public_dsa"]
            self.register_keys(user, public_kem, public_dsa)
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
                # Send the keys back to the person who prompted for the keys
                await sender_ws.send_text(json.dumps(response))
                print(f"Keys sent for {user}")

            else:
                status = {"type": "status", "message": f"No keys found for {user}"}
                await sender_ws.send_text(json.dumps(status))

    async def send_message(self, sender_ws, data):
        recipient = data["recipient"]
        if self.is_online(recipient):
            data["type"] = "message"
            await self.dict[recipient].send_text(json.dumps(data))
        else:
            data["type"] = "message"
            # Save to database instead of memory
            self.db.queue_message(recipient, json.dumps(data))
            print(f"Queued message for {recipient}")

    async def handle_account(self, sender_ws, data):
        username = data["username"]
        password = data["password"]

        if data["type"] == "register":
            # Success is the variable that will tell if there is a successful or failed attempt
            success = self.register_user(username, password)
            if success:
                response = {
                    "type": "account_response",
                    "success": True,
                    "message": "Account created"
                }
            else:
                response = {
                    "type": "account_response",
                    "success": False,
                    "message": "Username already taken"
                }
            await sender_ws.send_text(json.dumps(response))
        
        elif data["type"] == "login":
            success = self.login_user(username, password)
            if success:
                response = {
                    "type": "account_response",
                    "success": True,
                    "message": "Login successful"
                }
                await sender_ws.send_text(json.dumps(response))

                # Deliver queued messages AFTER login
                await self.deliver_queued(username, sender_ws)
            else:
                response = {
                    "type": "account_response",
                    "success": False,
                    "message": "Invalid username or password"
                }
                await sender_ws.send_text(json.dumps(response))

    async def deliver_queued(self, user, websocket):
        queued = self.db.get_queued_messages(user)
        if queued:
            for msg_id, msg_data in queued:
                await websocket.send_text(msg_data)
            print(f"Delivered {len(queued)} queued messages to {user}")
            self.db.delete_queued_messages(user)

    
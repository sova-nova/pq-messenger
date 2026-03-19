# client/main.py

import crypto_engine
from key_storage import KeyStore
from ws_client import WS_Client
import asyncio
import base64
import json
from prompt_toolkit import Application
from prompt_toolkit.layout import Layout, HSplit
from prompt_toolkit.widgets import TextArea, Frame
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.document import Document
from datetime import datetime


# These need to be accessible by multiple functions
message_area = TextArea(
    text="Welcome to PQ-Messenger\n",
    read_only=True,
    scrollbar=True,
)

input_area = TextArea(
    height=3,
    prompt=">>> ",
    multiline=False,
)

# Global variables that the key binding needs
ws = None
public_key = None
private_key = None
private_sig = None
recipient = None
recipient_keys = {}
pending_messages = []


def add_message(text):
    new_text = message_area.text + text + "\n"
    message_area.buffer.set_document(
        Document(text=new_text, cursor_position=len(new_text)),
        bypass_readonly=True,
    )


async def listen_for_messages(private_key):
    while True:
        try:
            response = await ws.receive_message()
            
            data = json.loads(response)
            # add_message(f"Type: {data.get('type')}")

            if data.get("type") == "status":
                add_message(f"[Server] {data['message']}")

            elif data.get("type") == "message":
                sender = data["sender"]
                add_message(f"[Sender] {sender}")
                if sender in recipient_keys:
                    sender_dsa = recipient_keys[sender]["public_dsa"]
                else:
                    # # Send message to waiting_queue for when you get keys back
                    # data["type"] = "wait"
                    # await ws.send_message(data)
                    pending_messages.append(data)
                    
                    # add_message(f"No signing key for {sender}, requesting...")
                    # Request their keys
                    request = {"type": "request_keys", "user": sender}
                    await ws.send_message(request)
                    continue
                
                add_message("Got to here")
                ciphertext = base64.b64decode(data["ciphertext"])
                payload = base64.b64decode(data["payload"])
                nonce = base64.b64decode(data["nonce"])
                signature = base64.b64decode(data["signature"])

                if crypto_engine.verifySignature(payload, sender_dsa, signature):
                    shared_secret = crypto_engine.decapsulate(ciphertext, private_key)
                    aes_key = crypto_engine.generateAES(shared_secret)
                    message = crypto_engine.decryptPayload(payload, nonce, aes_key)
                    sender = data.get("sender", "Unknown")
                    timestamp = data.get("timestamp", "")
                    if(timestamp):
                        t = datetime.fromisoformat(timestamp)
                        time_str = t.strftime("%H:%M")
                    else:
                        time_str = "??:??"

                    add_message(f"[{time_str}] [{sender}] {message.decode()}")
                else:
                    add_message("Signature invalid!")
            
            elif data.get("type") == "request_keys":
                user = data["user"]
                recipient_keys[user] = {
                    "public_kem": base64.b64decode(data["public_kem"]),
                    "public_dsa": base64.b64decode(data["public_dsa"])
                }
                
                # Process any pending messages from this user
                remaining = []
                for msg in pending_messages:
                    if msg.get("sender") == user:
                        # Now we have keys, process it
                        sender_dsa = recipient_keys[user]["public_dsa"]
                        
                        ciphertext = base64.b64decode(msg["ciphertext"])
                        payload = base64.b64decode(msg["payload"])
                        nonce = base64.b64decode(msg["nonce"])
                        signature = base64.b64decode(msg["signature"])
                        
                        if crypto_engine.verifySignature(payload, sender_dsa, signature):
                            shared_secret = crypto_engine.decapsulate(ciphertext, private_key)
                            aes_key = crypto_engine.generateAES(shared_secret)
                            message = crypto_engine.decryptPayload(payload, nonce, aes_key)
                            timestamp = msg.get("timestamp", "")
                            if timestamp:
                                t = datetime.fromisoformat(timestamp)
                                time_str = t.strftime("%H:%M")
                            else:
                                time_str = "??:??"
                            add_message(f"[{time_str}] [{user}] {message.decode()}")
                        else:
                            add_message("Signature invalid!")
                    else:
                        remaining.append(msg)
                pending_messages.clear()
                pending_messages.extend(remaining)

        except Exception as e:
            add_message(f"ERROR: {type(e).__name__}: {e}")
            continue    # ← don't break, keep listening


async def send_encrypted_message(message_text):
    global recipient

    if not recipient:
        add_message("Set recipient first with /to username")
        return
    
    # Check if we have recipient's keys
    if recipient not in recipient_keys:
        # add_message(f"Requesting {recipient}'s keys...")
        request = {"type": "request_keys", "user": recipient}
        await ws.send_message(request)
        # Wait briefly for the key response
        await asyncio.sleep(1)
        
        if recipient not in recipient_keys:
            add_message(f"Could not get keys for {recipient}")
            return

    recipient_kem = recipient_keys[recipient]["public_kem"]

    try:
        ciphertext, shared_secret = crypto_engine.encapsulate(recipient_kem, private_key)
        aes_key = crypto_engine.generateAES(shared_secret)
        payload, nonce = crypto_engine.symmetricEncryption(aes_key, message_text)
        signature = crypto_engine.createSignature(payload, private_sig)

        data = {
            "type": "message",
            "recipient": recipient,
            "sender": name,
            "ciphertext": base64.b64encode(ciphertext).decode(),
            "timestamp": datetime.now().isoformat(),
            "payload": base64.b64encode(payload).decode(),
            "nonce": base64.b64encode(nonce).decode(),
            "signature": base64.b64encode(signature).decode()
        }

        await ws.send_message(data)
        
        time_str = datetime.now().strftime("%H:%M")
        add_message(f"[{time_str}] [You → {recipient}] {message_text}")

    except Exception as e:
        add_message(f"Send error: {e}")


async def main():
    global ws, public_key, private_key, private_sig, recipient, name

    # Setup
    store = KeyStore()
    store.initialize_keys()
    public_key, private_key = store.load_kem_keypair()
    public_sig, private_sig = store.load_dsa_keypair()

    # Get connection info before starting UI
    # server = input("Server URL (press enter for localhost): ")
    server = "https://unwhite-lovetta-oozy.ngrok-free.dev" # Change this back to the line above for debugging on localhost
    if not server:
        server = "ws://localhost:8000"
    else:
        server = server.replace("https://", "").replace("http://", "").strip("/")
        server = f"wss://{server}"

    name = input("State your name: ")
    recipient = input("Default recipient: ")

    ws = WS_Client(server)
    await ws.client_connect(name)
    key_data = {
        "type": "register_keys",
        "user": name,
        "public_kem": base64.b64encode(public_key).decode(),
        "public_dsa": base64.b64encode(public_sig).decode()
    }
    await ws.send_message(key_data)

    key_request_data = {
        "type": "request_keys",
        "user": recipient
    }
    await ws.send_message(key_request_data)

    add_message(f"Connected as {name}")
    add_message(f"Sending to: {recipient}")
    add_message("Commands: /to <user> to change recipient, /quit to exit")
    add_message("")

    # Key bindings
    kb = KeyBindings()

    @kb.add("enter")
    def on_enter(event):
        text = input_area.text.strip()
        input_area.text = ""

        if not text:
            return

        if text == "/quit":
            event.app.exit()
            return

        if text.startswith("/to "):
            global recipient
            recipient = text[4:].strip()
            add_message(f"Now sending to: {recipient}")
            return

        asyncio.get_event_loop().create_task(
            send_encrypted_message(text)
        )

    @kb.add("c-c")
    def on_exit(event):
        event.app.exit()

    # When creating the Layout, set the focus on input_area:
    layout = Layout(
        HSplit([
            Frame(message_area, title=f"PQ-Messenger ({name})"),
            Frame(input_area, title=f"Message to {recipient}"),
        ]),
        focused_element=input_area,
    )

    # Create app
    app = Application(
        layout=layout,
        key_bindings=kb,
        full_screen=True,
        refresh_interval=0.5,
        mouse_support=True,        # ← add this
    )

    # Start listener in background
    listener = asyncio.create_task(
        listen_for_messages(private_key)
    )

    # Run the UI
    await app.run_async()

    # Cleanup
    listener.cancel()


if __name__ == "__main__":
    asyncio.run(main())
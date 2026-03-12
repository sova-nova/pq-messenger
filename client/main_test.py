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


def add_message(text):
    new_text = message_area.text + text + "\n"
    message_area.buffer.set_document(
        Document(text=new_text, cursor_position=len(new_text)),
        bypass_readonly=True,
    )


async def listen_for_messages(private_key, public_sig):
    while True:
        try:
            response = await ws.receive_message()
            
            data = json.loads(response)
            # add_message(f"Type: {data.get('type')}")

            if data.get("type") == "status":
                add_message(f"[Server] {data['message']}")

            elif data.get("type") == "message":
                ciphertext = base64.b64decode(data["ciphertext"])
                payload = base64.b64decode(data["payload"])
                nonce = base64.b64decode(data["nonce"])
                signature = base64.b64decode(data["signature"])

                if crypto_engine.verifySignature(payload, public_sig, signature):
                    shared_secret = crypto_engine.decapsulate(ciphertext, private_key)
                    aes_key = crypto_engine.generateAES(shared_secret)
                    message = crypto_engine.decryptPayload(payload, nonce, aes_key)
                    sender = data.get("sender", "Unknown")
                    add_message(f"[{sender}] {message.decode()}")
                else:
                    add_message("Signature invalid!")

        except Exception as e:
            add_message(f"ERROR: {type(e).__name__}: {e}")
            continue    # ← don't break, keep listening


async def send_encrypted_message(message_text):
    global recipient

    if not recipient:
        add_message("Set recipient first with /to username")
        return

    try:
        ciphertext, shared_secret = crypto_engine.encapsulate(public_key, private_key)
        aes_key = crypto_engine.generateAES(shared_secret)
        payload, nonce = crypto_engine.symmetricEncryption(aes_key, message_text)
        signature = crypto_engine.createSignature(payload, private_sig)

        data = {
            "recipient": recipient,
            "ciphertext": base64.b64encode(ciphertext).decode(),
            "payload": base64.b64encode(payload).decode(),
            "nonce": base64.b64encode(nonce).decode(),
            "signature": base64.b64encode(signature).decode()
        }

        await ws.send_message(data)
        add_message(f"[You → {recipient}] {message_text}")

    except Exception as e:
        add_message(f"Send error: {e}")    # ← add this


async def main():
    global ws, public_key, private_key, private_sig, recipient

    # Setup
    store = KeyStore()
    store.initialize_keys()
    public_key, private_key = store.load_kem_keypair()
    public_sig, private_sig = store.load_dsa_keypair()

    # Get connection info before starting UI
    server = input("Server URL (press enter for localhost): ")
    if not server:
        server = "ws://localhost:8000"
    else:
        server = server.replace("https://", "").replace("http://", "").strip("/")
        server = f"wss://{server}"

    name = input("State your name: ")
    recipient = input("Default recipient: ")

    ws = WS_Client(server)
    await ws.client_connect(name)

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
        listen_for_messages(private_key, public_sig)
    )

    # Run the UI
    await app.run_async()

    # Cleanup
    listener.cancel()


if __name__ == "__main__":
    asyncio.run(main())
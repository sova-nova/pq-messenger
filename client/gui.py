# client/gui.py

import flet as ft
import asyncio
import base64
import json
from datetime import datetime

# Import your existing modules
from ws_client import WS_Client
import crypto_engine
from key_storage import KeyStore
from known_keys import KnownKeys

async def main(page: ft.Page):
    page.title = "PQ-Messenger"
    page.window.width = 800
    page.window.height = 600

    # Global state
    ws = None
    conversations = {}  # username → list of message controls
    unread_counts = {}
    current_user = None
    current_recipient = None
    contact_buttons = {}
    public_key = None
    private_key = None
    public_sig = None
    private_sig = None
    recipient_keys = {}
    pending_messages = []
    known = KnownKeys()

    # Initialize keys
    store = KeyStore()
    store.initialize_keys()
    public_key, private_key = store.load_kem_keypair()
    public_sig, private_sig = store.load_dsa_keypair()

    # ══════════════════════════════════════
    # NETWORKING
    # ══════════════════════════════════════

    async def listen_for_messages():
        while True:
            try:
                response = await ws.receive_message()
                data = json.loads(response)

                if data.get("type") == "message":
                    sender = data["sender"]
                    
                    if sender in recipient_keys:
                        sender_dsa = recipient_keys[sender]["public_dsa"]
                    else:
                        pending_messages.append(data)
                        request = {"type": "request_keys", "user": sender}
                        await ws.send_message(request)
                        continue

                    ciphertext = base64.b64decode(data["ciphertext"])
                    payload = base64.b64decode(data["payload"])
                    nonce = base64.b64decode(data["nonce"])
                    signature = base64.b64decode(data["signature"])

                    if crypto_engine.verifySignature(payload, sender_dsa, signature):
                        shared_secret = crypto_engine.decapsulate(ciphertext, private_key)
                        aes_key = crypto_engine.generateAES(shared_secret)
                        message = crypto_engine.decryptPayload(payload, nonce, aes_key)
                        timestamp = data.get("timestamp", "")
                        
                        if timestamp:
                            t = datetime.fromisoformat(timestamp)
                            time_str = t.strftime("%H:%M")
                        else:
                            time_str = "??:??"

                        # Add to GUI
                        msg_control = ft.Text(
                            f"[{time_str}] {sender}: {message.decode()}",
                            color=ft.Colors.BLUE_200,
                        )

                        ensure_contact_exists(sender)

                        # Store in conversation
                        add_message_to_conversation(sender, msg_control)

                        # If not currently viewing this conversation, increment unread
                        if sender != current_recipient:
                            increment_unread(sender)
                            update_contact_display(sender)
                        else:
                            chat_messages.controls.append(msg_control)
                        
                        page.update()

                elif data.get("type") == "request_keys":
                    user = data["user"]
                    kem_public = base64.b64decode(data["public_kem"])
                    dsa_public = base64.b64decode(data["public_dsa"])

                    # TOFU check
                    if known.is_known(user):
                        if known.has_key_changed(user, kem_public, dsa_public):
                            # For now, just accept (later add confirmation dialog)
                            pass
                    else:
                        known.store_keys(user, kem_public, dsa_public)

                    recipient_keys[user] = {
                        "public_kem": kem_public,
                        "public_dsa": dsa_public
                    }

                    # Process pending messages
                    remaining = []
                    for msg in pending_messages:
                        if msg.get("sender") == user:
                            sender = msg.get("sender")
                            # Now we have their keys, decrypt this message
                            sender_dsa = recipient_keys[user]["public_dsa"]
                            
                            try:
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
                                    
                                    # Create message control
                                    msg_control = ft.Text(
                                        f"[{time_str}] {user}: {message.decode()}",
                                        color=ft.Colors.BLUE_200,
                                    )
                                    
                                    ensure_contact_exists(sender)
                                    
                                    # Store in conversation
                                    add_message_to_conversation(sender, msg_control)
                                    
                                    # Update unread if not viewing
                                    if user != current_recipient:
                                        increment_unread(user)
                                        update_contact_display(user)
                                    else:
                                        chat_messages.controls.append(msg_control)
                                        page.update()
                            
                            except Exception as e:
                                print(f"Error decrypting pending message: {e}")
                        else:
                            # Not from this user, keep in pending
                            remaining.append(msg)

                    pending_messages.clear()
                    pending_messages.extend(remaining)

                    pending_messages.clear()
                    pending_messages.extend(remaining)

            except Exception as e:
                print(f"Error in listener: {e}")
                await asyncio.sleep(1)

    async def send_encrypted_message(message_text):
        """Encrypt and send a message."""
        if not current_recipient:
            return

        if current_recipient not in recipient_keys:
            request = {"type": "request_keys", "user": current_recipient}
            await ws.send_message(request)
            await asyncio.sleep(1)

        if current_recipient not in recipient_keys:
            return

        recipient_kem = recipient_keys[current_recipient]["public_kem"]

        ciphertext, shared_secret = crypto_engine.encapsulate(recipient_kem, private_key)
        aes_key = crypto_engine.generateAES(shared_secret)
        payload, nonce = crypto_engine.symmetricEncryption(aes_key, message_text)
        signature = crypto_engine.createSignature(payload, private_sig)

        data = {
            "type": "message",
            "recipient": current_recipient,
            "sender": current_user,
            "ciphertext": base64.b64encode(ciphertext).decode(),
            "timestamp": datetime.now().isoformat(),
            "payload": base64.b64encode(payload).decode(),
            "nonce": base64.b64encode(nonce).decode(),
            "signature": base64.b64encode(signature).decode()
        }

        await ws.send_message(data)

    # ══════════════════════════════════════
    # LOGIN VIEW
    # ══════════════════════════════════════
    
    username_field = ft.TextField(label="Username", width=300)
    password_field = ft.TextField(label="Password", password=True, can_reveal_password=True, width=300)
    login_message = ft.Text("", color=ft.Colors.RED)

    async def do_login(e):
        nonlocal ws, current_user
        
        if not username_field.value or not password_field.value:
            login_message.value = "Enter username and password"
            page.update()
            return

        login_message.value = "Connecting..."
        page.update()

        # Connect to server
        server = "wss://127.0.0.0:8000"  # or localhost
        ws = WS_Client(server)
        await ws.client_connect(username_field.value)

        # Login
        data = {
            "type": "login",
            "username": username_field.value,
            "password": password_field.value
        }
        await ws.send_message(data)
        response = await ws.receive_message()
        result = json.loads(response)

        if result.get("success") == False:
            login_message.value = result.get("message", "Login failed")
            page.update()
            return

        current_user = username_field.value

        # Register keys
        key_data = {
            "type": "register_keys",
            "user": current_user,
            "public_kem": base64.b64encode(public_key).decode(),
            "public_dsa": base64.b64encode(public_sig).decode()
        }
        await ws.send_message(key_data)

        # Request queued messages
        await ws.send_message({"type": "request_queued"})

        # Start background listener
        page.run_task(listen_for_messages)

        # Show chat
        show_chat()

    async def do_register(e):
        # Similar to do_login but with register type
        pass

    login_view = ft.Column(
        [
            ft.Text("PQ-Messenger", size=30, weight=ft.FontWeight.BOLD),
            ft.Text("Post-Quantum Encrypted Messaging"),
            ft.Container(height=20),
            username_field,
            password_field,
            ft.Container(height=10),
            ft.Row(
                [
                    ft.Button("Login", on_click=do_login),
                    ft.Button("Register", on_click=do_register),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
            ),
            login_message,
        ],
        alignment=ft.MainAxisAlignment.CENTER,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
    )

    # ══════════════════════════════════════
    # CHAT VIEW
    # ══════════════════════════════════════

    contact_list = ft.ListView(width=150, spacing=5)
    chat_messages = ft.ListView(expand=True, spacing=10, auto_scroll=True)
    message_input = ft.TextField(hint_text="Type a message...", expand=True)

    async def send_message_click(e):
        if message_input.value and current_recipient:
            time_str = datetime.now().strftime("%H:%M")
            msg_control = ft.Text(f"[{time_str}] You: {message_input.value}")
        
            # Add to conversation storage
            add_message_to_conversation(current_recipient, msg_control)
            
            # Add to GUI if we're viewing this conversation
            chat_messages.controls.append(msg_control)
            
            # Send encrypted
            await send_encrypted_message(message_input.value)
            
            message_input.value = ""
            page.update()

    def select_contact(username):
        nonlocal current_recipient
        current_recipient = username
        chat_header.value = f"Chat with {username}"
        
        # Clear unread count
        clear_unread(username)
        update_contact_display(username)
        
        # Load messages
        chat_messages.controls.clear()
        if username in conversations:
            chat_messages.controls.extend(conversations[username])
    
        page.update()

    # Better approach: dynamically add contacts
    # when you receive a message from them

    def ensure_contact_exists(username):
        """Add contact if they don't exist in the list."""
        if username == current_user:
            return  # Don't add ourselves
        
        if username not in contact_buttons:
            add_contact(username)
            page.update()

    def add_contact(username):
            """Add a contact to the list."""
            def on_contact_click(e):
                select_contact(username)
            
            button = ft.TextButton(
                username,
                on_click=on_contact_click,
            )
            contact_buttons[username] = button
            contact_list.controls.append(button)

    def update_contact_display(username):
        """Update contact button to show unread count."""
        if username in contact_buttons:
            count = unread_counts.get(username, 0)
            if count > 0:
                contact_buttons[username].text = f"{username} ({count})"
                contact_buttons[username].style = ft.ButtonStyle(
                    color=ft.Colors.WHITE,
                    bgcolor=ft.Colors.BLUE_700,
                )
            else:
                contact_buttons[username].text = username
                contact_buttons[username].style = None
            page.update()

    def get_conversation(username):
        if username not in conversations:
            conversations[username] = []
        return conversations[username]

    def add_message_to_conversation(username, message_control):
        if username not in conversations:
            conversations[username] = []
        conversations[username].append(message_control)

    def increment_unread(username):
        if username not in unread_counts:
            unread_counts[username] = 0
        unread_counts[username] += 1

    def clear_unread(username):
        unread_counts[username] = 0

    

    chat_header = ft.Text("Select a contact", weight=ft.FontWeight.BOLD)

    chat_view = ft.Row(
        [
            ft.Container(
                content=ft.Column([
                    ft.Text("Contacts", weight=ft.FontWeight.BOLD),
                    contact_list,
                ]),
                width=150,
                bgcolor=ft.Colors.BLUE_GREY_900,
                padding=10,
            ),
            ft.Column(
                [
                    chat_header,
                    chat_messages,
                    ft.Row([
                        message_input,
                        ft.Button("Send", on_click=send_message_click)
                    ]),
                ],
                expand=True,
            ),
        ],
        expand=True,
    )

    # ══════════════════════════════════════
    # VIEW SWITCHING
    # ══════════════════════════════════════

    def show_login():
        page.controls.clear()
        page.add(
            ft.Container(
                content=login_view,
                expand=True,
                alignment=ft.Alignment.CENTER,
            )
        )
        page.update()

    def show_chat():
        chat_header.value = f"Logged in as {current_user}"
        
        # Add test contacts (but NOT yourself)
        # For now, hardcode some test users
        test_contacts = ["alice", "bob", "charlie"]
        for contact in test_contacts:
            if contact != current_user:  # ← Don't add yourself
                add_contact(contact)
        
        page.controls.clear()
        page.add(chat_view)
        page.update()

    # Start with login
    show_login()

ft.app(target=main)
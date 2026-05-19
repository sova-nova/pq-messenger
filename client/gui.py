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
from session import Session  # ← New import

async def main(page: ft.Page):
    page.title = "PQ-Messenger"
    page.window.width = 800
    page.window.height = 600

    # Single session object instead of many globals
    session = Session()
    known = KnownKeys()

    # Initialize keys
    store = KeyStore()
    store.initialize_keys()
    session.public_key, session.private_key = store.load_kem_keypair()
    session.public_sig, session.private_sig = store.load_dsa_keypair()

    # ══════════════════════════════════════
    # NETWORKING
    # ══════════════════════════════════════

    async def listen_for_messages():
        while True:
            try:
                response = await session.ws.receive_message()
                data = json.loads(response)

                if data.get("type") == "message":
                    sender = data["sender"]
                    
                    if sender in session.recipient_keys:
                        sender_dsa = session.recipient_keys[sender]["public_dsa"]
                    else:
                        session.pending_messages.append(data)
                        request = {"type": "request_keys", "user": sender}
                        await session.ws.send_message(request)
                        continue

                    ciphertext = base64.b64decode(data["ciphertext"])
                    payload = base64.b64decode(data["payload"])
                    nonce = base64.b64decode(data["nonce"])
                    signature = base64.b64decode(data["signature"])

                    if crypto_engine.verifySignature(payload, sender_dsa, signature):
                        shared_secret = crypto_engine.decapsulate(ciphertext, session.private_key)
                        aes_key = crypto_engine.generateAES(shared_secret)
                        message = crypto_engine.decryptPayload(payload, nonce, aes_key)
                        timestamp = data.get("timestamp", "")
                        
                        if timestamp:
                            t = datetime.fromisoformat(timestamp)
                            time_str = t.strftime("%H:%M")
                        else:
                            time_str = "??:??"

                        msg_control = create_received_bubble(sender, message.decode(), time_str)
                        ensure_contact_exists(sender)
                        session.add_message(sender, msg_control)

                        # Save to history
                        session.save_text_message(
                            sender,
                            message.decode(),
                            is_sent=False,
                            timestamp=data.get("timestamp")
                        )

                        if sender != session.current_recipient:
                            session.increment_unread(sender)
                            update_contact_display(sender)
                        else:
                            chat_messages.controls.append(msg_control)
                        
                        page.update()

                elif data.get("type") == "search_result":
                    username = data["username"]
                    print(f"Search result: {username}")
                    if data["found"] == True:
                        add_contact_input.hint_text = "Found!"
                        ensure_contact_exists(username)
                        await session.ws.send_message({
                            "type": "request_keys",
                            "user": username
                        })
                    else:
                        add_contact_input.hint_text = f"Not found"
                    page.update()

                elif data.get("type") == "request_keys":
                    user = data["user"]
                    kem_public = base64.b64decode(data["public_kem"])
                    dsa_public = base64.b64decode(data["public_dsa"])

                    # TOFU check
                    if known.is_known(user):
                        if known.has_key_changed(user, kem_public, dsa_public):
                            pass  # TODO: Add confirmation dialog
                    else:
                        known.store_keys(user, kem_public, dsa_public)

                    session.recipient_keys[user] = {
                        "public_kem": kem_public,
                        "public_dsa": dsa_public
                    }

                    # Process pending messages
                    remaining = []
                    for msg in session.pending_messages:
                        if msg.get("sender") == user:
                            sender = msg.get("sender")
                            sender_dsa = session.recipient_keys[user]["public_dsa"]
                            
                            try:
                                ciphertext = base64.b64decode(msg["ciphertext"])
                                payload = base64.b64decode(msg["payload"])
                                nonce = base64.b64decode(msg["nonce"])
                                signature = base64.b64decode(msg["signature"])
                                
                                if crypto_engine.verifySignature(payload, sender_dsa, signature):
                                    shared_secret = crypto_engine.decapsulate(ciphertext, session.private_key)
                                    aes_key = crypto_engine.generateAES(shared_secret)
                                    message = crypto_engine.decryptPayload(payload, nonce, aes_key)
                                    
                                    timestamp = msg.get("timestamp", "")
                                    if timestamp:
                                        t = datetime.fromisoformat(timestamp)
                                        time_str = t.strftime("%H:%M")
                                    else:
                                        time_str = "??:??"
                                    
                                    msg_control = create_received_bubble(user, message.decode(), time_str)
                                    ensure_contact_exists(sender)
                                    session.add_message(sender, msg_control)
                                    
                                    if user != session.current_recipient:
                                        session.increment_unread(user)
                                        update_contact_display(user)
                                    else:
                                        chat_messages.controls.append(msg_control)
                                        page.update()
                            
                            except Exception as e:
                                print(f"Error decrypting pending message: {e}")
                        else:
                            remaining.append(msg)

                    session.pending_messages.clear()
                    session.pending_messages.extend(remaining)

            except Exception as e:
                print(f"Error in listener: {e}")
                await asyncio.sleep(1)

    async def send_encrypted_message(message_text):
        """Encrypt and send a message."""
        if not session.current_recipient:
            return

        if session.current_recipient not in session.recipient_keys:
            request = {"type": "request_keys", "user": session.current_recipient}
            await session.ws.send_message(request)
            await asyncio.sleep(1)

        if session.current_recipient not in session.recipient_keys:
            return

        recipient_kem = session.recipient_keys[session.current_recipient]["public_kem"]

        ciphertext, shared_secret = crypto_engine.encapsulate(recipient_kem, session.private_key)
        aes_key = crypto_engine.generateAES(shared_secret)
        payload, nonce = crypto_engine.symmetricEncryption(aes_key, message_text)
        signature = crypto_engine.createSignature(payload, session.private_sig)

        data = {
            "type": "message",
            "recipient": session.current_recipient,
            "sender": session.username,
            "ciphertext": base64.b64encode(ciphertext).decode(),
            "timestamp": datetime.now().isoformat(),
            "payload": base64.b64encode(payload).decode(),
            "nonce": base64.b64encode(nonce).decode(),
            "signature": base64.b64encode(signature).decode()
        }

        await session.ws.send_message(data)

    def validate_password(password):
        if len(password) < 8:
            return False, "Password must be at least 8 characters"
        if not any(c.isupper() for c in password):
            return False, "Password must contain an uppercase letter"
        if not any(c.islower() for c in password):
            return False, "Password must contain a lowercase letter"
        if not any(c.isdigit() for c in password):
            return False, "Password must contain a number"
        return True, "Password accepted"

    # ══════════════════════════════════════
    # LOGIN VIEW
    # ══════════════════════════════════════
    
    username_field = ft.TextField(label="Username", width=300)
    password_field = ft.TextField(label="Password", password=True, can_reveal_password=True, width=300)
    login_message = ft.Text("", color=ft.Colors.RED)

    async def do_login(e):
        if not username_field.value or not password_field.value:
            login_message.value = "Enter username and password"
            page.update()
            return

        login_message.value = "Connecting..."
        page.update()

        server = "ws://127.0.0.1:8000"
        session.ws = WS_Client(server)
        await session.ws.client_connect(username_field.value)

        data = {
            "type": "login",
            "username": username_field.value,
            "password": password_field.value
        }
        await session.ws.send_message(data)
        response = await session.ws.receive_message()
        result = json.loads(response)

        if result.get("success") == False:
            login_message.value = result.get("message", "Login failed")
            page.update()
            return

        session.username = username_field.value
        session.is_authenticated = True
        session.load_contacts()  # ← Load contacts AFTER username is set

        key_data = {
            "type": "register_keys",
            "user": session.username,
            "public_kem": base64.b64encode(session.public_key).decode(),
            "public_dsa": base64.b64encode(session.public_sig).decode()
        }
        await session.ws.send_message(key_data)
        await session.ws.send_message({"type": "request_queued"})

        page.run_task(listen_for_messages)
        show_chat()

    async def do_register(e):
        if not username_field.value or not password_field.value:
            login_message.value = "Enter username and password"
            page.update()
            return

        valid, msg = validate_password(password_field.value)
        if not valid:
            login_message.value = msg
            page.update()
            return

        login_message.value = "Connecting..."
        page.update()

        server = "ws://127.0.0.1:8000"
        session.ws = WS_Client(server)
        await session.ws.client_connect(username_field.value)

        data = {
            "type": "register",
            "username": username_field.value,
            "password": password_field.value
        }
        await session.ws.send_message(data)
        response = await session.ws.receive_message()
        result = json.loads(response)

        if result.get("success") == False:
            login_message.value = result.get("message", "Registration failed")
            page.update()
            return

        session.username = username_field.value
        session.is_authenticated = True
        session.load_contacts()  # ← Load contacts AFTER username is set

        key_data = {
            "type": "register_keys",
            "user": session.username,
            "public_kem": base64.b64encode(session.public_key).decode(),
            "public_dsa": base64.b64encode(session.public_sig).decode()
        }
        await session.ws.send_message(key_data)
        await session.ws.send_message({"type": "request_queued"})

        page.run_task(listen_for_messages)
        show_chat()

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
        if message_input.value and session.current_recipient:
            time_str = datetime.now().strftime("%H:%M")
            timestamp = datetime.now().isoformat()
            msg_control = create_sent_bubble(message_input.value, time_str)
            
            session.add_message(session.current_recipient, msg_control)
            chat_messages.controls.append(msg_control)
            
            # Save to history
            session.save_text_message(
                session.current_recipient, 
                message_input.value, 
                is_sent=True,
                timestamp=timestamp
            )
            
            await send_encrypted_message(message_input.value)
            
            message_input.value = ""
            page.update()

    def select_contact(username):
        session.current_recipient = username
        chat_header.value = f"Chat with {username}"
        
        session.clear_unread(username)
        update_contact_display(username)
        
        chat_messages.controls.clear()
        
        # Load from in-memory conversation first
        if username in session.conversations:
            chat_messages.controls.extend(session.conversations[username])
        else:
            # Load from persistent history
            history = session.load_message_history(username)
            session.conversations[username] = []
            
            for msg in history:
                if msg["type"] == "text":
                    time_str = datetime.fromisoformat(msg["timestamp"]).strftime("%H:%M")
                    if msg["is_sent"]:
                        bubble = create_sent_bubble(msg["text"], time_str)
                    else:
                        bubble = create_received_bubble(msg["sender"], msg["text"], time_str)
                    
                    session.conversations[username].append(bubble)
                    chat_messages.controls.append(bubble)
        
        page.update()

    def ensure_contact_exists(username):
        """Add contact if they don't exist in the list."""
        if username == session.username:
            return
        
        if session.add_contact(username):  # ← Uses session method
            add_contact_to_ui(username)
            page.update()
        elif username not in session.contact_buttons:
            # Contact was already in saved list but not in UI
            add_contact_to_ui(username)
            page.update()

    def add_contact_to_ui(username):
        """Add a contact button to the UI."""
        def on_contact_click(e):
            select_contact(username)
        
        button = ft.TextButton(username, on_click=on_contact_click)
        session.contact_buttons[username] = button
        contact_list.controls.append(button)

    def update_contact_display(username):
        """Update contact button to show unread count."""
        if username in session.contact_buttons:
            count = session.get_unread(username)
            if count > 0:
                session.contact_buttons[username].content = f"{username} ({count})"
                session.contact_buttons[username].style = ft.ButtonStyle(
                    color=ft.Colors.WHITE,
                    bgcolor=ft.Colors.BLUE_700,
                )
            else:
                session.contact_buttons[username].text = username
                session.contact_buttons[username].style = None
            page.update()

    def create_sent_bubble(text, time_str):
        bubble = ft.Container(
            content=ft.Column([
                ft.Text("You", size=10, color=ft.Colors.GREY_300, weight=ft.FontWeight.BOLD),
                ft.Text(text, size=14, color=ft.Colors.WHITE),
                ft.Text(time_str, size=9, color=ft.Colors.GREY_400, text_align=ft.TextAlign.RIGHT),
            ]),
            bgcolor=ft.Colors.BLUE_700,
            border_radius=ft.BorderRadius.all(10),
            padding=10,
        )
        return ft.Row([bubble], alignment=ft.MainAxisAlignment.END)

    def create_received_bubble(sender, text, time_str):
        bubble = ft.Container(
            content=ft.Column([
                ft.Text(sender, size=10, color=ft.Colors.GREY_300, weight=ft.FontWeight.BOLD),
                ft.Text(text, size=14, color=ft.Colors.WHITE),
                ft.Text(time_str, size=9, color=ft.Colors.GREY_400),
            ]),
            bgcolor=ft.Colors.BLUE_GREY_800,
            border_radius=ft.BorderRadius.all(10),
            padding=10,
        )
        return ft.Row([bubble], alignment=ft.MainAxisAlignment.START)

    add_contact_input = ft.TextField(
        hint_text="Add user...",
        width=100,
        text_size=12,
        content_padding=5
    )

    async def on_add_contact_click(e):
        target = add_contact_input.value.strip()
        if target:
            if target == session.username:
                add_contact_input.hint_text = "It's you!"
                add_contact_input.value = ""
                page.update()
                return
            
            data = {"type": "search_user", "username": target}
            await session.ws.send_message(data)
            add_contact_input.value = ""
            add_contact_input.hint_text = "Searching..."
            page.update()

    chat_header = ft.Text("Select a contact", weight=ft.FontWeight.BOLD)

    chat_view = ft.Row(
        [
            ft.Container(
                content=ft.Column([
                    ft.Text("Contacts", weight=ft.FontWeight.BOLD),
                    ft.Row([
                        add_contact_input,
                        ft.IconButton(
                            icon=ft.Icons.ADD,
                            on_click=on_add_contact_click,
                            icon_size=20
                        )
                    ], spacing=0),
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
        chat_header.value = f"Logged in as {session.username}"
        
        # Load saved contacts
        for contact in session.contacts:
            add_contact_to_ui(contact)
        
        page.controls.clear()
        page.add(chat_view)
        page.update()

    show_login()

ft.app(target=main)
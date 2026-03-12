import crypto_engine
from key_storage import KeyStore
from ws_client import WS_Client
import asyncio
from aioconsole import ainput
import base64
import json

### Main client file ###

async def listen_for_messages(websocket, private_key, public_sig):
    while True:
        try:
            response = await websocket.receive_message()
            data = json.loads(response)

            if data.get("type") == "status":
                print(f"\n[Server] {data['message']}")

            if data.get("type") == "message":
                ciphertext = base64.b64decode(data["ciphertext"])
                payload = base64.b64decode(data["payload"])
                nonce = base64.b64decode(data["nonce"])
                signature = base64.b64decode(data["signature"])

                if(crypto_engine.verifySignature(payload, public_sig, signature)):
                    shared_secret_recipient = crypto_engine.decapsulate(ciphertext, private_key)
                    aesKEY = crypto_engine.generateAES(shared_secret_recipient)
                    message = crypto_engine.decryptPayload(payload, nonce, aesKEY)
                    print(f"\n{message.decode()}")
                else:
                    print("Signature is unverified!")
                    break

        except Exception as e:
            print(f"Disconnected: {e}")
            break

async def handle_user_input(ws, public_key, private_key, private_sig):
    while True:
        try:
            recipient = await ainput("To: ")
            message = await ainput("Message: ")

            ciphertext, shared_secret_sender = crypto_engine.encapsulate(public_key, private_key)
            aesKEY = crypto_engine.generateAES(shared_secret_sender)
            payload, nonce = crypto_engine.symmetricEncryption(aesKEY, message)
            signature = crypto_engine.createSignature(payload, private_sig)

            data = {
                "type": "message",
                "recipient": recipient,
                "ciphertext": base64.b64encode(ciphertext).decode(),
                "payload": base64.b64encode(payload).decode(),
                "nonce": base64.b64encode(nonce).decode(),
                "signature": base64.b64encode(signature).decode()
            }
            
            await ws.send_message(data)
            # response = await ws.receive_message()
            # print(response)

        except Exception:
            break

async def main():
    server = "https://unwhite-lovetta-oozy.ngrok-free.dev"
    if not server:
        server = "ws://localhost:8000"
    else:
        # Clean up the URL
        server = server.replace("https://", "").replace("http://", "").strip("/")
        server = f"wss://{server}"

    ws = WS_Client(server)
    store = KeyStore()

    # Initialize Keys
    store.initialize_keys()

    # Key generation invocation
    public_key, private_key = store.load_kem_keypair()
    public_sig, private_sig = store.load_dsa_keypair()

    # Message and connection details
    name = input("State your name: ")
    await ws.client_connect(name)

    listener = asyncio.create_task(
        listen_for_messages(ws, private_key, public_sig)
    )

    sender = asyncio.create_task(
        handle_user_input(ws, public_key, private_key, private_sig)
    )

    done, pending = await asyncio.wait(
        [listener, sender],
        return_when=asyncio.FIRST_COMPLETED
    )

    for task in pending:
        task.cancel()

    # while True:
    #     action = input("(s)end or (r)eceive or (q)uit: ")

    #     if action == "s":
    #         message = input("Message to send: ")
    #         recipient = input("Recipient name: ")

    #         ciphertext, shared_secret_sender = crypto_engine.encapsulate(public_key, private_key)
    #         aesKEY = crypto_engine.generateAES(shared_secret_sender)
    #         payload, nonce = crypto_engine.symmetricEncryption(aesKEY, message)
    #         signature = crypto_engine.createSignature(payload, private_sig)

    #         data = {
    #             "recipient": recipient,
    #             "ciphertext": base64.b64encode(ciphertext).decode(),
    #             "payload": base64.b64encode(payload).decode(),
    #             "nonce": base64.b64encode(nonce).decode(),
    #             "signature": base64.b64encode(signature).decode()
    #         }
            
    #         await ws.send_message(data)
    #         response = await ws.receive_message()
    #         print(response)

    #     elif action == "r":
    #         response = await ws.receive_message()
    #         data = json.loads(response)

    #         ciphertext = base64.b64decode(data["ciphertext"])
    #         payload = base64.b64decode(data["payload"])
    #         nonce = base64.b64decode(data["nonce"])
    #         signature = base64.b64decode(data["signature"])

    #         if(crypto_engine.verifySignature(payload, public_sig, signature)):
    #             shared_secret_recipient = crypto_engine.decapsulate(ciphertext, private_key)
    #             aesKEY = crypto_engine.generateAES(shared_secret_recipient)
    #             message = crypto_engine.decryptPayload(payload, nonce, aesKEY)
    #             print(message.decode())
    #         else:
    #             print("Signature is unverified!")
    #             break
        
    #     elif action == "q":
    #         break
        
if __name__ == "__main__":
    asyncio.run(main())
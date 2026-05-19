# client/crypto_engine.py
import os
import oqs
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

# Generate a kem keypair
def generate_kem_keypair():
    # Initialize ML-KEM-768
    kem = oqs.KeyEncapsulation("ML-KEM-768")

    public_key = kem.generate_keypair()
    private_key = kem.export_secret_key()

    # print("Public Key: " + public_key.hex() + " END")
    # print("Private Key: " + private_key.hex() + " END")
    
    return public_key, private_key

# Generate a signing keypair
def generate_sig_keypair():
    # Initialize ML-KEM-768
    sig = oqs.Signature("ML-DSA-65")

    public_key = sig.generate_keypair()
    private_key = sig.export_secret_key()
    
    return public_key, private_key

# ML-KEM Encapsulation Technique
# Generates a shared secret and ciphertext with the recipient's public key
def encapsulate(public_key, private_key):
    ### Base code from https://qramm.org/learn/ml-kem-kyber-explained.html ###

    kem = oqs.KeyEncapsulation("ML-KEM-768", secret_key=private_key)

    # Sender encapsulates a shared secret
    ciphertext, shared_secret_sender = kem.encap_secret(public_key)
    # print(f"Ciphertext size: {len(ciphertext)} bytes")

    return ciphertext, shared_secret_sender

# HKDF Generation Technique
def generateAES(shared_secret):
    salt = None
    info = b"pq-messenger"
    hkdf = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        info=info,
    )

    return hkdf.derive(shared_secret)

# Symmetric Encryption with AESGCM
def symmetricEncryption(aesKey, message):
    aad = None # b"authenticated but unencrypted data"
    aesgcm = AESGCM(aesKey)
    nonce = os.urandom(12)
    payload = aesgcm.encrypt(nonce, message.encode(), aad)
    # aesgcm.decrypt(nonce, ct, aad)

    return payload, nonce

# Create a signature with the ML-DSA-65 algorithm
def createSignature(payload, private_sig):
    sig = oqs.Signature("ML-DSA-65", secret_key=private_sig)
    signature = sig.sign(payload)

    return signature

# Decryption Steps

# Verify the signature with the ML-DSA-65 algorithm
def verifySignature(payload, public_sig, signature):
    sig = oqs.Signature("ML-DSA-65")
    verifier = sig.verify(payload, signature, public_sig)
    
    return verifier

###
# Later, remove the shared_secret_sender from the arguments and remove the verification of shared_secret
###
def decapsulate(ciphertext, private_key):
    # Initialize ML-KEM-768
    kem = oqs.KeyEncapsulation("ML-KEM-768", secret_key=private_key)

    # Recipient decapsulates to get the same shared secret
    shared_secret_recipient = kem.decap_secret(ciphertext)
    
    return shared_secret_recipient

# Generate AES

def decryptPayload(payload, nonce, aesKey):
    aad = None
    aesgcm = AESGCM(aesKey)
    message = aesgcm.decrypt(nonce, payload, aad)

    return message
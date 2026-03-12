# client/key_store.py

from pathlib import Path
import oqs

class KeyStore:

    def __init__(self):
        self.path = Path.home() / ".pq-messenger" / "keys"
        self.path.mkdir(parents=True, exist_ok=True)

    def generate_keypairs(self):
        # Initialize ML-KEM-768
        kem = oqs.KeyEncapsulation("ML-KEM-768")

        public_kem = kem.generate_keypair()
        private_kem = kem.export_secret_key()

        (self.path / "public_kem").write_bytes(public_kem)
        (self.path / "private_kem").write_bytes(private_kem)

        # Initialize ML-KEM-768
        sig = oqs.Signature("ML-DSA-65")

        public_dsa = sig.generate_keypair()
        private_dsa = sig.export_secret_key()

        (self.path / "public_dsa").write_bytes(public_dsa)
        (self.path / "private_dsa").write_bytes(private_dsa)
        
        return

    def load_kem_keypair(self):
        return (self.path / "public_kem").read_bytes(), (self.path / "private_kem").read_bytes()

    def load_dsa_keypair(self):
        return (self.path / "public_dsa").read_bytes(), (self.path / "private_dsa").read_bytes()
    
    def initialize_keys(self):
        if((self.path / "public_kem").exists() and (self.path / "private_kem").exists() and (self.path / "public_dsa").exists() and (self.path / "private_dsa").exists()):
            print("Keys have already been generated!")
            return
        else:
            self.delete_keys()
            self.generate_keypairs()
            print("Keys have been regenerated!")
            return
            

    def delete_keys(self):
        (self.path / "public_kem").unlink(missing_ok=True)
        (self.path / "private_kem").unlink(missing_ok=True)
        (self.path / "public_dsa").unlink(missing_ok=True)
        (self.path / "private_dsa").unlink(missing_ok=True)
        print("All old keys have been deleted!")

        return





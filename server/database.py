# server/database.py

import sqlite3
from pathlib import Path

class Database:
    def __init__(self):
        self.db_path = Path(__file__).parent / "messenger.db"
        self.create_tables()

    def create_tables(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS accounts (
                username TEXT PRIMARY KEY,
                password_hash TEXT NOT NULL
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS keys (
                username TEXT PRIMARY KEY,
                kem_public_key TEXT NOT NULL,
                dsa_public_key TEXT NOT NULL,
                FOREIGN KEY (username) REFERENCES accounts(username)
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS queued_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                recipient TEXT NOT NULL,
                message_data TEXT NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (recipient) REFERENCES accounts(username)
            )
        """)

    def register_user(self, username, password_hash):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        try:
            cursor.execute(
                "INSERT INTO accounts (username, password_hash) VALUES (?, ?)",
                (username, password_hash)
            )
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            # Username already exists
            return False
        finally:
            conn.close()

    def get_password_hash(self, username):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT password_hash FROM accounts WHERE username = ?",
            (username,)
        )
        result = cursor.fetchone()
        conn.close()
        if result:
            return result[0]
        return None

    def store_keys(self, username, kem_public, dsa_public):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO keys (username, kem_public_key, dsa_public_key)
            VALUES (?, ?, ?)
            ON CONFLICT(username) DO UPDATE SET
                kem_public_key = ?,
                dsa_public_key = ?
        """, (username, kem_public, dsa_public, kem_public, dsa_public))
        conn.commit()
        conn.close()

    def get_keys(self, username):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT kem_public_key, dsa_public_key FROM keys WHERE username = ?",
            (username,)
        )
        result = cursor.fetchone()
        conn.close()
        if result:
            return {
                "public_kem": result[0],
                "public_dsa": result[1]
            }
        return None

    def queue_message(self, recipient, message_json):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO queued_messages (recipient, message_data) VALUES (?, ?)",
            (recipient, message_json)
        )
        conn.commit()
        conn.close()

    def get_queued_messages(self, recipient):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, message_data FROM queued_messages WHERE recipient = ?",
            (recipient,)
        )
        results = cursor.fetchall()
        conn.close()
        return results

    def delete_queued_messages(self, recipient):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "DELETE FROM queued_messages WHERE recipient = ?",
            (recipient,)
        )
        conn.commit()
        conn.close()
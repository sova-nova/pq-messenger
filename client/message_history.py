# client/message_history.py

from pathlib import Path
import json
from datetime import datetime
from typing import List, Dict, Optional
import base64

class MessageHistory:
    def __init__(self, username: str):
        self.username = username
        self.history_dir = Path.home() / ".pq-messenger" / "history"
        self.history_dir.mkdir(parents=True, exist_ok=True)
    
    def _get_conversation_path(self, contact: str) -> Path:
        """Get the file path for a conversation."""
        # Sort usernames to ensure same file regardless of who initiated
        users = sorted([self.username, contact])
        filename = f"{users[0]}_{users[1]}.json"
        return self.history_dir / filename
    
    def save_message(self, contact: str, message_data: dict):
        """Save a single message to history."""
        path = self._get_conversation_path(contact)
        
        # Load existing messages
        messages = []
        if path.exists():
            try:
                with open(path, 'r') as f:
                    messages = json.load(f)
            except Exception as e:
                print(f"Error loading history: {e}")
        
        # Add new message
        messages.append(message_data)
        
        # Keep only last 1000 messages (configurable)
        if len(messages) > 1000:
            messages = messages[-1000:]
        
        # Save
        try:
            with open(path, 'w') as f:
                json.dump(messages, f, indent=2)
        except Exception as e:
            print(f"Error saving message: {e}")
    
    def load_conversation(self, contact: str) -> List[dict]:
        """Load all messages for a conversation."""
        path = self._get_conversation_path(contact)
        
        if not path.exists():
            return []
        
        try:
            with open(path, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading conversation: {e}")
            return []
    
    def delete_conversation(self, contact: str):
        """Delete conversation history."""
        path = self._get_conversation_path(contact)
        path.unlink(missing_ok=True)
    
    def get_all_conversations(self) -> List[str]:
        """Get list of all contacts with history."""
        contacts = set()
        for file in self.history_dir.glob("*.json"):
            users = file.stem.split('_')
            for user in users:
                if user != self.username:
                    contacts.add(user)
        return sorted(contacts)
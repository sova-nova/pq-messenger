# client/session.py

from dataclasses import dataclass, field
from typing import Dict, List, Optional
import flet as ft
from pathlib import Path
import json

@dataclass
class Session:
    """Manages application state and persistent data."""
    
    # Authentication
    username: Optional[str] = None
    is_authenticated: bool = False
    
    # Keys
    public_key: Optional[bytes] = None
    private_key: Optional[bytes] = None
    public_sig: Optional[bytes] = None
    private_sig: Optional[bytes] = None
    
    # Networking
    ws: Optional[object] = None
    
    # Contacts & Messages
    contacts: List[str] = field(default_factory=list)
    conversations: Dict[str, List] = field(default_factory=dict)
    unread_counts: Dict[str, int] = field(default_factory=dict)
    recipient_keys: Dict[str, dict] = field(default_factory=dict)
    pending_messages: List[dict] = field(default_factory=list)
    
    # UI State
    current_recipient: Optional[str] = None
    contact_buttons: Dict[str, ft.TextButton] = field(default_factory=dict)
    
    def __post_init__(self):
        self.contacts_path = Path.home() / ".pq-messenger" / "contacts.json"
        self.contacts_path.parent.mkdir(parents=True, exist_ok=True)
        self.load_contacts()
    
    def load_contacts(self):
        """Load saved contacts from disk."""
        if self.contacts_path.exists():
            try:
                with open(self.contacts_path, 'r') as f:
                    data = json.load(f)
                    self.contacts = data.get('contacts', [])
                    print(f"Loaded {len(self.contacts)} contacts")
            except Exception as e:
                print(f"Error loading contacts: {e}")
                self.contacts = []
    
    def save_contacts(self):
        """Save contacts to disk."""
        try:
            with open(self.contacts_path, 'w') as f:
                json.dump({'contacts': self.contacts}, f, indent=2)
            print(f"Saved {len(self.contacts)} contacts")
        except Exception as e:
            print(f"Error saving contacts: {e}")
    
    def add_contact(self, username: str) -> bool:
        """Add a contact if not already present."""
        if username not in self.contacts and username != self.username:
            self.contacts.append(username)
            self.save_contacts()
            return True
        return False
    
    def remove_contact(self, username: str):
        """Remove a contact."""
        if username in self.contacts:
            self.contacts.remove(username)
            self.save_contacts()
    
    def get_conversation(self, username: str) -> List:
        """Get or create conversation history."""
        if username not in self.conversations:
            self.conversations[username] = []
        return self.conversations[username]
    
    def add_message(self, username: str, message_control):
        """Add a message to a conversation."""
        self.get_conversation(username).append(message_control)
    
    def increment_unread(self, username: str):
        """Increment unread count for a contact."""
        if username not in self.unread_counts:
            self.unread_counts[username] = 0
        self.unread_counts[username] += 1
    
    def clear_unread(self, username: str):
        """Clear unread count for a contact."""
        self.unread_counts[username] = 0
    
    def get_unread(self, username: str) -> int:
        """Get unread count for a contact."""
        return self.unread_counts.get(username, 0)
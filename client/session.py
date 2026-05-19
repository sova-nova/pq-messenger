# client/session.py

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional
import flet as ft
from pathlib import Path
import json
from message_history import MessageHistory

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
    message_history: Optional[MessageHistory] = None
    
    
    # UI State
    current_recipient: Optional[str] = None
    contact_buttons: Dict[str, ft.TextButton] = field(default_factory=dict)
    
    def __post_init__(self):
        self.contacts_dir = Path.home() / ".pq-messenger" / "user_data"
        self.contacts_dir.mkdir(parents=True, exist_ok=True)
        # Don't load contacts yet - we don't know the username
    
    def _get_contacts_path(self) -> Path:
        """Get the contacts file path for the current user."""
        if not self.username:
            raise ValueError("Username not set")
        return self.contacts_dir / f"{self.username}_contacts.json"
    
    def load_message_history(self, contact: str) -> List[dict]:
        """Load message history for a contact."""
        if not self.message_history:
            return []
        return self.message_history.load_conversation(contact)
    
    def load_contacts(self):
        """Load saved contacts from disk for the current user."""
        if not self.username:
            print("Cannot load contacts: username not set")
            return
        
        # Initialize message history
        self.message_history = MessageHistory(self.username)
        
        contacts_path = self._get_contacts_path()
        if contacts_path.exists():
            try:
                with open(contacts_path, 'r') as f:
                    data = json.load(f)
                    self.contacts = data.get('contacts', [])
                    print(f"Loaded {len(self.contacts)} contacts for {self.username}")
            except Exception as e:
                print(f"Error loading contacts: {e}")
                self.contacts = []
        else:
            print(f"No saved contacts found for {self.username}")
            self.contacts = []
    
    def save_contacts(self):
        """Save contacts to disk for the current user."""
        if not self.username:
            print("Cannot save contacts: username not set")
            return
        
        try:
            contacts_path = self._get_contacts_path()
            with open(contacts_path, 'w') as f:
                json.dump({'contacts': self.contacts}, f, indent=2)
            print(f"Saved {len(self.contacts)} contacts for {self.username}")
        except Exception as e:
            print(f"Error saving contacts: {e}")

    def save_text_message(self, contact: str, text: str, is_sent: bool, timestamp: str = None):
        """Save a text message to history."""
        if not self.message_history:
            return
        
        message_data = {
            "type": "text",
            "text": text,
            "sender": self.username if is_sent else contact,
            "recipient": contact if is_sent else self.username,
            "timestamp": timestamp or datetime.now().isoformat(),
            "is_sent": is_sent
        }
        
        self.message_history.save_message(contact, message_data)
    
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
    
    def clear_session(self):
        """Clear all session data (for logout)."""
        self.contacts = []
        self.conversations = {}
        self.unread_counts = {}
        self.recipient_keys = {}
        self.pending_messages = []
        self.current_recipient = None
        self.contact_buttons = {}
        self.is_authenticated = False
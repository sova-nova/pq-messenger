# client/session.py

from dataclasses import dataclass, field
from typing import Dict, List, Optional
import flet as ft
from pathlib import Path
import json
from datetime import datetime

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
    
    # Privacy settings
    persistent_contacts: set = field(default_factory=set)  # Contacts with persistent history enabled
    message_history: Optional[object] = None
    
    # UI State
    current_recipient: Optional[str] = None
    contact_buttons: Dict[str, ft.TextButton] = field(default_factory=dict)
    
    def __post_init__(self):
        self.contacts_dir = Path.home() / ".pq-messenger" / "user_data"
        self.contacts_dir.mkdir(parents=True, exist_ok=True)
    
    def _get_contacts_path(self) -> Path:
        """Get the contacts file path for the current user."""
        if not self.username:
            raise ValueError("Username not set")
        return self.contacts_dir / f"{self.username}_contacts.json"
    
    def _get_settings_path(self) -> Path:
        """Get the settings file path for the current user."""
        if not self.username:
            raise ValueError("Username not set")
        return self.contacts_dir / f"{self.username}_settings.json"
    
    def load_contacts(self):
        """Load saved contacts from disk for the current user."""
        if not self.username:
            print("Cannot load contacts: username not set")
            return
        
        # Initialize message history
        from message_history import MessageHistory
        self.message_history = MessageHistory(self.username)
        
        # Load contacts
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
        
        # Load settings (including persistent_contacts)
        self.load_settings()
    
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
    
    def load_settings(self):
        """Load user settings including persistent chat preferences."""
        settings_path = self._get_settings_path()
        if settings_path.exists():
            try:
                with open(settings_path, 'r') as f:
                    data = json.load(f)
                    self.persistent_contacts = set(data.get('persistent_contacts', []))
                    print(f"Loaded settings: {len(self.persistent_contacts)} persistent chats")
            except Exception as e:
                print(f"Error loading settings: {e}")
                self.persistent_contacts = set()
        else:
            self.persistent_contacts = set()
    
    def save_settings(self):
        """Save user settings including persistent chat preferences."""
        if not self.username:
            return
        
        try:
            settings_path = self._get_settings_path()
            data = {
                'persistent_contacts': list(self.persistent_contacts)
            }
            with open(settings_path, 'w') as f:
                json.dump(data, f, indent=2)
            print(f"Saved settings: {len(self.persistent_contacts)} persistent chats")
        except Exception as e:
            print(f"Error saving settings: {e}")
    
    def is_persistent(self, contact: str) -> bool:
        """Check if chat history is persistent for this contact."""
        return contact in self.persistent_contacts
    
    def enable_persistence(self, contact: str):
        """Enable persistent history for a contact."""
        if contact not in self.persistent_contacts:
            self.persistent_contacts.add(contact)
            self.save_settings()
            print(f"Enabled persistent history for {contact}")
    
    def disable_persistence(self, contact: str):
        """Disable persistent history for a contact and optionally delete history."""
        if contact in self.persistent_contacts:
            self.persistent_contacts.remove(contact)
            self.save_settings()
            print(f"Disabled persistent history for {contact}")
    
    def delete_history(self, contact: str):
        """Delete persistent history for a contact."""
        if self.message_history:
            self.message_history.delete_conversation(contact)
            print(f"Deleted history for {contact}")
    
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
    
    def save_text_message(self, contact: str, text: str, is_sent: bool, timestamp: str = None):
        """Save a text message to history (only if persistence is enabled)."""
        if not self.message_history:
            return
        
        # Only save if persistence is enabled for this contact
        if not self.is_persistent(contact):
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
    
    def load_message_history(self, contact: str) -> List[dict]:
        """Load message history for a contact (only if persistence is enabled)."""
        if not self.message_history:
            return []
        
        # Only load if persistence is enabled for this contact
        if not self.is_persistent(contact):
            return []
        
        return self.message_history.load_conversation(contact)
    
    def clear_session(self):
        """Clear all session data (for logout)."""
        self.contacts = []
        self.conversations = {}
        self.unread_counts = {}
        self.recipient_keys = {}
        self.pending_messages = []
        self.current_recipient = None
        self.contact_buttons = {}
        self.persistent_contacts = set()
        self.is_authenticated = False
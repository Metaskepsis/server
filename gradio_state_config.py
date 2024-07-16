import os
from dataclasses import dataclass, asdict
import json
from typing import List, Optional


# Server configuration
SERVER_HOST = "127.0.0.1"  # or "0.0.0.0" if you want to make it accessible from other machines
SERVER_PORT = 7860  # or any other port you prefer

# API configuration
API_BASE_URL = "http://localhost:8000"  # Replace with your actual API base URL

# Logging configuration
LOG_LEVEL = "INFO"  # You can change this to "DEBUG" for more detailed logs

# File upload configuration
MAX_UPLOAD_SIZE = 20 * 1024 * 1024  # 20 MB

# Other constants
DEFAULT_PROJECT_NAME = "New Project"
MAX_CHAT_HISTORY = 50  # Maximum number of messages to keep in chat history

# Tab names
LOGIN_TAB = "Login/Register"
PROJECT_TAB = "Project Management"
LLM_TAB = "LLM Interface"

# Project actions
CREATE_NEW_PROJECT = "Create New Project"
CHOOSE_EXISTING_PROJECT = "Choose Existing Project"

# File types allowed for upload
ALLOWED_FILE_TYPES = ['text/plain', 'application/pdf', 'application/json', 'application/xml']

@dataclass
class State:
    token: str = ""
    username: str = ""
    project: str = ""
    selected_file: str = ""
    chat_history: List[dict] =  None
    project_creation_chat_history: List[dict] = None
    
    def __post_init__(self):
        if self.chat_history is None:
            self.chat_history = []
        if self.project_creation_chat_history is None:
            self.project_creation_chat_history = []

    def to_json(self) -> str:
        return json.dumps(asdict(self))

    @classmethod
    def from_json(cls, json_str: str) -> 'State':
        data = json.loads(json_str)
        return cls(**data)

    def update(self, **kwargs) -> None:
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)

    def clear(self) -> None:
        self.token = ""
        self.username = ""
        self.project = ""
        self.selected_file = ""
        self.chat_history = []
        self.project_creation_chat_history = []

    def add_chat_message(self, role: str, content: str, is_project_creation: bool = False) -> None:
        if is_project_creation:
            self.project_creation_chat_history.append({"role": role, "content": content})
            if len(self.project_creation_chat_history) > MAX_CHAT_HISTORY:
                self.project_creation_chat_history.pop(0)
        else:
            self.chat_history.append({"role": role, "content": content})
            if len(self.chat_history) > MAX_CHAT_HISTORY:
                self.chat_history.pop(0)

def get_env_variable(name: str, default: Optional[str] = None) -> str:
    """Retrieve an environment variable or return a default value."""
    return os.getenv(name, default)

# Environment-specific configurations
DEBUG = get_env_variable('DEBUG', 'False').lower() == 'true'
SECRET_KEY = get_env_variable('SECRET_KEY', 'your-secret-key')

# Database configuration (if needed)
DB_HOST = get_env_variable('DB_HOST', 'localhost')
DB_PORT = int(get_env_variable('DB_PORT', '5432'))
DB_NAME = get_env_variable('DB_NAME', 'your_db_name')
DB_USER = get_env_variable('DB_USER', 'your_db_user')
DB_PASSWORD = get_env_variable('DB_PASSWORD', 'your_db_password')

# Function to initialize state
def initialize_state() -> State:
    return State()

# Function to get current state (you might want to implement this differently based on your needs)
def get_current_state() -> State:
    # This is a placeholder. In a real application, you might retrieve this from a database or session
    return initialize_state()

# Additional configurations can be added here as needed
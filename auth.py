import os
import json
from fastapi import HTTPException, status, Depends
from fastapi.security import OAuth2PasswordBearer
from passlib.context import CryptContext
from pydantic import BaseModel, Field, field_validator
from typing import Optional, Union
from datetime import datetime, timedelta, timezone
from jose import JWTError, jwt
from dotenv import load_dotenv
import shutil
import re
import logging
import requests

# Load environment variables from .env file
load_dotenv()

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
SECRET_KEY = os.getenv("SECRET_KEY")  # Secret key for JWT encoding/decoding
ALGORITHM = "HS256"  # Algorithm used for JWT encoding/decoding
ACCESS_TOKEN_EXPIRE_MINUTES = 30  # Token expiration time in minutes
USERS_DIRECTORY = "./users"  # Directory to store user data

# Create users directory if it doesn't exist
os.makedirs(USERS_DIRECTORY, exist_ok=True)

# Set up password hashing context and OAuth2 scheme
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# Pydantic models for data validation and serialization
class Token(BaseModel):
    """Model for JWT token response."""
    access_token: str
    token_type: str

class TokenData(BaseModel):
    """Model for JWT token payload."""
    username: Optional[str] = None

class UserBase(BaseModel):
    """Base model for user data."""
    username: str

class UserCreate(BaseModel):
    username: str
    password: str
    gemini_api_key: str

    @field_validator('username')
    def username_valid(cls, v):
        if not validate_username(v):
            raise ValueError('Invalid username format')
        return v

    @field_validator('password')
    def password_valid(cls, v):
        if not validate_password(v):
            raise ValueError('Invalid password format')
        return v

    @field_validator('gemini_api_key')
    def gemini_api_key_valid(cls, v):
        if not validate_gemini_api_key(v):
            raise ValueError('Invalid Gemini API key')
        return v

class UserInDB(UserBase):
    """Model for user data stored in the database."""
    hashed_password: str
    gemini_api_key: str
    disabled: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_login: Optional[datetime] = None

class User(UserBase):
    """Model for user data returned to the client."""
    disabled: bool = False

# Helper functions
def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain password against a hashed password."""
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    """Generate a hash for the given password."""
    return pwd_context.hash(password)

def user_exists(username: str) -> bool:
    """Check if a user with the given username already exists."""
    user_file = os.path.join(USERS_DIRECTORY, username, "credentials.json")
    return os.path.exists(user_file)

def validate_username(username: str) -> bool:
    """Validate username criteria."""
    # Username should be alphanumeric and between 6 to 20 characters
    return bool(re.match(r'^[a-zA-Z0-9_]{6,20}$', username))

def validate_password(password: str) -> bool:
    """Validate password criteria."""
    # Password should be at least 8 characters long, contain upper and lowercase letters, a digit, and a special character
    return bool(re.match(r'^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&])[A-Za-z\d@$!%*?&]{8,}$', password))

def get_user(username: str) -> Optional[UserInDB]:
    """Retrieve user data from the user's credentials file."""
    user_file = os.path.join(USERS_DIRECTORY, username, "credentials.json")
    if not os.path.exists(user_file):
        logger.warning(f"User {username} does not exist")
        return None
    
    try:
        with open(user_file, "r") as f:
            user_dict = json.load(f)
        
        required_fields = ["username", "hashed_password", "gemini_api_key"]
        for field in required_fields:
            if field not in user_dict:
                raise ValueError(f"Missing required field: {field}")
        
        user_dict["created_at"] = datetime.fromisoformat(user_dict.get("created_at")) if user_dict.get("created_at") else datetime.now(timezone.utc)
        user_dict["last_login"] = datetime.fromisoformat(user_dict.get("last_login")) if user_dict.get("last_login") else None
        
        return UserInDB(**user_dict)
    except (json.JSONDecodeError, ValueError) as e:
        logger.error(f"Error loading user data for {username}: {str(e)}")
        return None

def authenticate_user(username: str, password: str) -> Union[UserInDB, bool]:
    user = get_user(username)
    if not user:
        logger.warning(f"Authentication failed: User {username} does not exist")
        return False
    if not verify_password(password, user.hashed_password):
        logger.warning(f"Authentication failed: Incorrect password for user {username}")
        return False
    return user

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create a JWT access token."""
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=15))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def register_user(user: UserCreate) -> UserInDB:
    """Register a new user."""
    
    user_dir = os.path.join(USERS_DIRECTORY, user.username)
    os.makedirs(os.path.join(user_dir, "projects"), exist_ok=True)
    
    hashed_password = get_password_hash(user.password)
    user_dict = {
        "username": user.username,
        "hashed_password": hashed_password,
        "disabled": False,
        "gemini_api_key": user.gemini_api_key,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "last_login": None
    }
    
    with open(os.path.join(user_dir, "credentials.json"), "w") as f:
        json.dump(user_dict, f)
    
    return UserInDB(**user_dict)

def update_user_last_login(username: str):
    """Update the user's last login time."""
    user_file = os.path.join(USERS_DIRECTORY, username, "credentials.json")
    with open(user_file, "r+") as f:
        user_data = json.load(f)
        user_data["last_login"] = datetime.now(timezone.utc).isoformat()
        f.seek(0)
        json.dump(user_data, f, default=str)
        f.truncate()

async def get_current_user(token: str = Depends(oauth2_scheme)) -> UserInDB:
    """Get the current user based on the provided JWT token."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
        token_data = TokenData(username=username)
    except JWTError:
        raise credentials_exception
    user = get_user(username=token_data.username)
    if user is None:
        raise credentials_exception
    return user

async def get_current_active_user(current_user: UserInDB = Depends(get_current_user)) -> UserInDB:
    """Get the current active user."""
    if current_user.disabled:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user



def get_user_api_key(username: str) -> str:
    """Get the user's current Gemini API key."""
    user_file = os.path.join(USERS_DIRECTORY, username, "credentials.json")
    try:
        with open(user_file, "r") as f:
            user_data = json.load(f)
        return user_data.get("gemini_api_key", "")
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to retrieve API key: {str(e)}")

def validate_gemini_api_key(api_key: str) -> bool:
    """Validate the Gemini API key by making a test request."""
    if not api_key or not api_key.strip():
        logger.error("Empty API key provided")
        return False
    
    url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent"
    headers = {
        "Content-Type": "application/json",
        "x-goog-api-key": api_key
    }
    data = {
        "contents": [{"parts":[{"text": "Hello, are you working?"}]}]
    }
    
    try:
        logger.info(f"Attempting to validate Gemini API key: {api_key[:5]}...")  # Log first 5 characters of API key
        response = requests.post(url, headers=headers, json=data, timeout=10)
        response.raise_for_status()
        logger.info("Gemini API key validation successful")
        return True
    except requests.RequestException as e:
        logger.error(f"Error validating Gemini API key: {str(e)}")
        if hasattr(e, 'response'):
            logger.error(f"Response status code: {e.response.status_code}")
            logger.error(f"Response content: {e.response.text}")
        return False

def get_username_from_token(token: str) -> str:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise ValueError("Username not found in token")
        return username
    except JWTError:
        raise ValueError("Invalid token")
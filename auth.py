import os
import json
from fastapi import HTTPException, status, Depends
from fastapi.security import OAuth2PasswordBearer
from passlib.context import CryptContext
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timedelta
from jose import JWTError, jwt
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configuration
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "fallback_secret_key_for_development_only")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

USERS_DIRECTORY = "./users"

if not os.path.exists(USERS_DIRECTORY):
    os.makedirs(USERS_DIRECTORY)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None

class UserCreate(BaseModel):
    username: str
    email: str
    password: str
    gemini_api_key: str

class User(BaseModel):
    username: str
    email: str
    full_name: Optional[str] = ""
    disabled: Optional[bool] = False

class UserInDB(User):
    hashed_password: str
    gemini_api_key: str

def get_user(username: str):
    user_file = os.path.join(USERS_DIRECTORY, username, "credentials.json")
    if not os.path.exists(user_file):
        return None
    with open(user_file, "r") as f:
        user_dict = json.load(f)
    return UserInDB(**user_dict)

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

def authenticate_user(username: str, password: str):
    user = get_user(username)
    if not user:
        return False
    if not verify_password(password, user.hashed_password):
        return False
    return user

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def register_user(user: UserCreate):
    user_dir = os.path.join(USERS_DIRECTORY, user.username)
    if os.path.exists(user_dir):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already exists"
        )
    
    try:
        os.makedirs(user_dir)
        projects_dir = os.path.join(user_dir, "projects")
        os.makedirs(projects_dir)
        
        hashed_password = get_password_hash(user.password)
        user_dict = {
            "username": user.username,
            "email": user.email,
            "full_name": "",
            "hashed_password": hashed_password,
            "disabled": False,
            "gemini_api_key": user.gemini_api_key  # Store the API key
        }
        
        with open(os.path.join(user_dir, "credentials.json"), "w") as f:
            json.dump(user_dict, f)
        
        return {"message": "User registered successfully"}
    except Exception as e:
        # If any error occurs during registration, remove the partially created user directory
        if os.path.exists(user_dir):
            for root, dirs, files in os.walk(user_dir, topdown=False):
                for name in files:
                    os.remove(os.path.join(root, name))
                for name in dirs:
                    os.rmdir(os.path.join(root, name))
            os.rmdir(user_dir)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error during registration: {str(e)}"
        )

async def get_current_user(token: str = Depends(oauth2_scheme)):
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

async def get_current_active_user(current_user: User = Depends(get_current_user)):
    if current_user.disabled:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user
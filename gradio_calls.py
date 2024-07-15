import aiohttp
from aiohttp import FormData
import json
from typing import Dict, Any, Optional, Callable, List, Tuple
from functools import wraps
from dataclasses import dataclass
import logging
import os
import mimetypes
import asyncio

# Constants
API_URL = "http://localhost:8000"
DEFAULT_ERROR_MESSAGE = "An unexpected error occurred"

# Custom exceptions
class APIError(Exception):
    """Base exception for API-related errors."""
    pass

class AuthenticationError(APIError):
    """Exception raised for authentication-related errors."""
    pass

@dataclass
class APIResponse:
    """Data class to standardize API responses."""
    success: bool
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def make_api_request(method: str, endpoint: str, token: Optional[str] = None, json_data: Optional[Dict] = None, data: Optional[Dict] = None, files: Optional[Dict] = None):
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    url = f"{API_URL}/{endpoint}"
    
    logger.info(f"Making {method} request to {url} with token: {token[:5] if token else 'None'}...")

    async with aiohttp.ClientSession() as session:
        try:
            if files:
                # Handle file uploads
                form_data = FormData()
                for key, file_tuple in files.items():
                    form_data.add_field(key, file_tuple[1], filename=file_tuple[0], content_type=file_tuple[2])
                request_kwargs = {"data": form_data}
            elif json_data:
                request_kwargs = {"json": json_data}
            elif data:
                request_kwargs = {"data": data}
            else:
                request_kwargs = {}

            async with session.request(method, url, headers=headers, **request_kwargs, timeout=10) as response:
                try:
                    response_json = await response.json()
                except json.JSONDecodeError:
                    response_text = await response.text()
                    logger.error(f"Failed to decode JSON from response. Text content: {response_text}")
                    response_json = {"detail": response_text}

                if response.status >= 400:
                    error_detail = response_json.get('detail', str(response_json))
                    if response.status == 401:
                        raise AuthenticationError("Not authenticated")
                    else:
                        raise APIError(f"HTTP error {response.status}: {error_detail}")

                return response_json

        except aiohttp.ClientError as e:
            logger.error(f"Client error in API request: {str(e)}")
            raise APIError(f"An error occurred: {str(e)}")



def api_call_with_error_handling(func: Callable) -> Callable:
    @wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except aiohttp.ClientResponseError as e:
            error_detail = await e.response.json()
            error_detail = error_detail.get("detail", str(e))
            logger.error(f"HTTP error in {func.__name__}: {error_detail}")
            raise
        except aiohttp.ClientConnectorError as e:
            logger.error(f"Connection error in {func.__name__}: {str(e)}")
            return APIResponse(success=False, error="Connection error. Please check your internet connection.")
        except asyncio.TimeoutError as e:
            logger.error(f"Timeout error in {func.__name__}: {str(e)}")
            return APIResponse(success=False, error="Request timed out. Please try again later.")
        except aiohttp.ClientError as e:
            logger.error(f"Request error in {func.__name__}: {str(e)}")
            return APIResponse(success=False, error=f"An error occurred: {str(e)}")
    return wrapper

@api_call_with_error_handling
async def login_api_call(username: str, password: str, new_api_key: str) -> Tuple[str, str, bool, str]:
    try:
        data = {
            "username": username,
            "password": password,
        }
        
        # If a new API key is provided, include it in the request
        if new_api_key:
            data["scope"] = new_api_key
        
        response = await make_api_request('POST', 'token', data=data)
        
        if isinstance(response, dict) and "access_token" in response:
            access_token = response["access_token"]
            message = "Login successful"
            if new_api_key:
                message += ". Gemini API key updated."
            elif "api_key_status" in response:
                if response["api_key_status"] == "valid":
                    message += ". Existing Gemini API key is valid."
                else:
                    message += ". Existing Gemini API key is invalid or missing. Please update it."
            return access_token, message, True, username
        else:
            return "", "Login failed: Invalid response from server", False, ""
    except AuthenticationError as e:
        return "", f"Login failed: {str(e)}", False, ""
    except APIError as e:
        return "", f"Login failed: {str(e)}", False, ""

@api_call_with_error_handling
async def register_api_call(username: str, password: str, gemini_api_key: str) -> APIResponse:
    """Register a new user."""
    data = {
        "username": username,
        "password": password,
        "gemini_api_key": gemini_api_key
    }
    try:
        response = await make_api_request('POST', 'register', json_data=data)
        return APIResponse(success=True, data=response)
    except APIError as e:
        error_msg = str(e)
        if "Invalid Gemini API key" in error_msg:
            return APIResponse(success=False, error="The provided Gemini API key is invalid.")
        elif "Username already exists" in error_msg:
            return APIResponse(success=False, error="This username is already taken. Please choose a different one.")
        elif "Invalid username format" in error_msg:
            return APIResponse(success=False, error="Invalid username format. Username must be between 6 and 20 characters.")
        elif "Invalid password format" in error_msg:
            return APIResponse(success=False, error="Invalid password format. Password must be at least 8 characters long, contain uppercase and lowercase letters, a digit, and a special character.")
        else:
            return APIResponse(success=False, error=f"Registration failed: {error_msg}")

@api_call_with_error_handling
async def list_files(token: str, project_name: str) -> Dict[str, List[str]]:
    if not token:
        logger.error(f"Attempted to list files for project '{project_name}' without a token")
        raise AuthenticationError("No token provided")
    
    try:
        logger.info(f"Attempting to list files for project '{project_name}' with token")
        response = await make_api_request('GET', f'projects/{project_name}/files', token=token)
        logger.info(f"Received response for project '{project_name}': {response}")
        if isinstance(response, dict):
            return {
                "main": response.get("main", []),
                "temp": response.get("temp", [])
            }
        else:
            logger.warning(f"Unexpected response type from list_files for project '{project_name}': {type(response)}")
            return {"main": [], "temp": []}
    except AuthenticationError as e:
        logger.error(f"Authentication failed when listing files for project '{project_name}': {str(e)}")
        raise
    except Exception as e:
        logger.error(f"Error listing files for project '{project_name}': {str(e)}")
        raise

@api_call_with_error_handling
async def upload_file(token: str, project_name: str, file_path: str) -> Dict[str, str]:
    """Upload a file to a specific project."""
    if not os.path.exists(file_path):
        logger.warning(f"File not found: {file_path}")
        return {"status": "error", "message": "File not found."}
    
    try:
        # Check file size
        file_size = os.path.getsize(file_path)
        if file_size > 20 * 1024 * 1024:  # 20MB in bytes
            logger.warning(f"File {file_path} is too large ({file_size / (1024 * 1024):.2f} MB)")
            return {"status": "error", "message": "File is too big. Maximum allowed size is 20MB."}

        # Check file type
        mime_type, _ = mimetypes.guess_type(file_path)
        text_types = ['text/', 'application/pdf', 'application/json', 'application/xml']
        if not any(mime_type.startswith(text_type) for text_type in text_types):
            logger.warning(f"Invalid file type: {mime_type}")
            return {"status": "error", "message": "Invalid file type. Only text files, PDFs, JSONs, and XMLs are allowed."}

        # Read file content
        with open(file_path, "rb") as f:
            content = f.read()
            if not content:
                logger.warning("Attempted to upload an empty file")
                return {"status": "error", "message": "The selected file is empty. Please choose a file with content."}
            
            # Upload to temp folder
            temp_folder = f"temp/{project_name}"
            files = {'file': (os.path.basename(file_path), content, mime_type)}
            response = await make_api_request('POST', f'upload/{temp_folder}', token, files=files)
            
            if response.get("message"):
                return {"status": "success", "message": response["message"]}
            else:
                return {"status": "error", "message": "File upload failed due to an unknown error"}
    except Exception as e:
        logger.error(f"Error during file upload: {str(e)}")
        return {"status": "error", "message": f"An error occurred during file upload: {str(e)}"}

@api_call_with_error_handling
async def update_api_key(token: str, new_api_key: str) -> APIResponse:
    """Update the user's Gemini API key."""
    response = await make_api_request('POST', 'users/me/update_api_key', token, json={"new_api_key": new_api_key})
    if isinstance(response, dict) and "message" in response:
        return APIResponse(success=True, data=response)
    return APIResponse(success=False, error="new_api_key is not valid")

@api_call_with_error_handling
async def list_projects(token: str) -> List[Dict[str, str]]:
    """Fetch the list of projects with their timestamps for the current user."""
    try:
        return await make_api_request('GET', 'projects', token)
    except AuthenticationError:
        logger.warning("Authentication failed when listing projects. Returning empty list.")
        return []
    except Exception as e:
        logger.error(f"Error listing projects: {str(e)}")
        return []

@api_call_with_error_handling
async def create_project(token: str, project_name: str) -> Dict[str, Any]:
    """Create a new project."""
    try:
        data = {"project_name": project_name}
        response = await make_api_request('POST', 'projects', token, json=data)
        if isinstance(response, dict) and "message" in response:
            return response
        else:
            raise APIError("Unexpected response format from create_project API")
    except Exception as e:
        logger.error(f"Error creating project: {str(e)}")
        raise APIError(f"Failed to create project: {str(e)}")


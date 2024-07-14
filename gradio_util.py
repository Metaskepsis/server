# gradio_util.py

import gradio as gr
import logging
from functools import wraps
from typing import List, Tuple, Dict, Any, Optional, Callable
from dataclasses import dataclass
import requests
import os
import json
from datetime import datetime

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

def api_call_with_error_handling(func: Callable) -> Callable:
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except requests.HTTPError as e:
            # Log the error but re-raise it to be handled by the specific function
            error_detail = e.response.json().get("detail", str(e))
            logger.error(f"HTTP error in {func.__name__}: {error_detail}")
            raise
        except requests.ConnectionError as e:
            logger.error(f"Connection error in {func.__name__}: {str(e)}")
            return APIResponse(success=False, error="Connection error. Please check your internet connection.")
        except requests.Timeout as e:
            logger.error(f"Timeout error in {func.__name__}: {str(e)}")
            return APIResponse(success=False, error="Request timed out. Please try again later.")
        except requests.RequestException as e:
            logger.error(f"Request error in {func.__name__}: {str(e)}")
            return APIResponse(success=False, error=f"An error occurred: {str(e)}")
    return wrapper

def refresh_token(refresh_token: str) -> Optional[str]:
    """Attempt to refresh the access token using the refresh token."""
    try:
        response = requests.post(f"{API_URL}/token/refresh", json={"refresh_token": refresh_token})
        response.raise_for_status()
        return response.json().get("access_token")
    except requests.RequestException:
        return None

def make_api_request(method: str, endpoint: str, token: Optional[str] = None, json: Optional[Dict] = None, data: Optional[Dict] = None, files: Optional[Dict] = None):
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    url = f"{API_URL}/{endpoint}"
    
    try:
        response = requests.request(method, url, headers=headers, json=json, data=data, files=files, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.HTTPError as e:
        if e.response.content:
            try:
                error_data = e.response.json()
                if isinstance(error_data, list) and error_data:
                    error_detail = error_data[0].get('msg', str(e))
                elif isinstance(error_data, dict):
                    error_detail = error_data.get('detail', str(e))
                else:
                    error_detail = str(e)
                raise APIError(error_detail)
            except ValueError:
                raise APIError(str(e))
        else:
            raise APIError(str(e))
    except requests.exceptions.RequestException as e:
        raise APIError(f"An error occurred: {str(e)}")

@api_call_with_error_handling
def login_api_call(username: str, password: str, new_api_key: str) -> Tuple[str, str, bool, str]:
    try:
        data = {
            "username": username,
            "password": password,
            "scope": new_api_key  # Pass the new API key in the scope field
        }
        response = make_api_request('POST', 'token', data=data)
        
        if isinstance(response, dict) and "access_token" in response:
            access_token = response["access_token"]
            message = "Login successful"
            if new_api_key:
                message += ". Gemini API key updated."
            return access_token, message, True, username
        else:
            return "", "Login failed: Invalid response from server", False, ""
    except requests.exceptions.HTTPError as e:
        error_detail = e.response.json().get("detail", str(e))
        return "", f"Login failed: {error_detail}", False, ""
    except requests.exceptions.RequestException as e:
        return "", f"Login failed: {str(e)}", False, ""

api_call_with_error_handling
def register_api_call(username: str, password: str, gemini_api_key: str) -> APIResponse:
    """Register a new user."""
    data = {
        "username": username,
        "password": password,
        "gemini_api_key": gemini_api_key
    }
    try:
        response = make_api_request('POST', 'register', json=data)
        return APIResponse(success=True, data=response)
    except APIError as e:
        error_msg = str(e)
        if "Invalid Gemini API key" in error_msg:
            error_msg = "Invalid Gemini API key"
        return APIResponse(success=False, error=error_msg)


@api_call_with_error_handling
def list_files(token: str, project_name: str) -> Dict[str, List[str]]:
    """Fetch the list of files for a given project."""
    try:
        response = make_api_request('GET', f'projects/{project_name}/files', token)
        if not isinstance(response, dict):
            logger.warning(f"Unexpected response type from list_files: {type(response)}")
            return {"main": [], "temp": []}
        return {
            "main": response.get("main", []),
            "temp": response.get("temp", [])
        }
    except AuthenticationError:
        logger.warning("Authentication failed when listing files. Returning empty dict.")
        return {"main": [], "temp": []}
    except Exception as e:
        logger.error(f"Error listing files: {str(e)}")
        return {"main": [], "temp": []}

@api_call_with_error_handling
def upload_file(token: str, project_name: str, file: gr.File) -> Dict[str, str]:
    """Upload a file to a specific project."""
    if file is None:
        raise ValueError("No file selected")
    
    with file.open("rb") as f:
        files = {'file': (file.name, f, getattr(file, 'type', 'application/octet-stream'))}
        return make_api_request('POST', f'upload/{project_name}', token, files=files)

@api_call_with_error_handling
def update_api_key(token: str, new_api_key: str) -> APIResponse:
    """Update the user's Gemini API key."""
    response = make_api_request('POST', 'users/me/update_api_key', token, json={"new_api_key": new_api_key})
    if isinstance(response, dict) and "message" in response:
        return APIResponse(success=True, data=response)
    return APIResponse(success=False, error="new_api_key is not valid")

@api_call_with_error_handling
def list_projects(token: str) -> List[Dict[str, str]]:
    """Fetch the list of projects with their timestamps for the current user."""
    try:
        return make_api_request('GET', 'projects', token)
    except AuthenticationError:
        logger.warning("Authentication failed when listing projects. Returning empty list.")
        return []
    except Exception as e:
        logger.error(f"Error listing projects: {str(e)}")
        return []

@api_call_with_error_handling
def create_project(token: str, project_name: str) -> Dict[str, Any]:
    """Create a new project with 'main' and 'temp' folders."""
    data = {"project_name": project_name}
    response = make_api_request('POST', 'projects', token, json=data)
    
    if isinstance(response, dict) and "message" in response:
        # Project created successfully, now create 'main' and 'temp' folders
        try:
            make_api_request('POST', f'projects/{project_name}/folders', token, json={"folder_name": "main"})
            make_api_request('POST', f'projects/{project_name}/folders', token, json={"folder_name": "temp"})
            return {"message": f"Project '{project_name}' created successfully with 'main' and 'temp' folders"}
        except Exception as e:
            logger.error(f"Error creating folders for project {project_name}: {str(e)}")
            return {"message": f"Project '{project_name}' created, but failed to create 'main' and 'temp' folders"}
    
    return response  # Return the original response if project creation failed



def handle_login_result(token: str, message: str, success: bool, username: str) -> Tuple[str, str, gr.update, gr.update, gr.update, str, gr.update, str, gr.update]:
    if success:
        try:
            projects = list_projects(token)
            if not projects:
                return (token, username, *update_visibility(False, True, False), message, update_dropdown([]), "", gr.update())
            else:
                most_recent_project = projects[0]["name"]
                return (
                    token, 
                    username, 
                    *update_visibility(False, False, True), 
                    message, 
                    update_dropdown([p["name"] for p in projects], value=most_recent_project), 
                    most_recent_project,
                    gr.update(value=f"## Current Project: {most_recent_project}")  # Update the project name in LLM tab
                )
        except Exception as e:
            logger.error(f"Error fetching projects: {str(e)}")
            return (token, username, *update_visibility(False, True, False), f"{message} (Error fetching projects)", update_dropdown([]), "", gr.update())
    return ("", "", *update_visibility(True, False, False), message, update_dropdown([]), "", gr.update())

def update_visibility(login_visible: bool, project_visible: bool, llm_visible: bool) -> Tuple[gr.update, gr.update, gr.update]:
    """Update the visibility of main interface tabs."""
    return tuple(gr.update(visible=v) for v in (login_visible, project_visible, llm_visible))

def update_dropdown(choices: List[str], value: Optional[str] = None) -> gr.update:
    """Update a Gradio dropdown component."""
    return gr.update(choices=choices, value=value)

def validate_token(token: str) -> bool:
    """Validate the token by making a test request."""
    try:
        make_api_request('GET', 'users/me', token)
        return True
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 401:
            return False
        else:
            raise
    except Exception:
        return False
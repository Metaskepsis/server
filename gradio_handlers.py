import gradio as gr
from gradio_state_config import *
import gradio_calls as api
import logging
from typing import Dict, List, Tuple
import json


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def handle_login(username: str, password: str, new_api_key: str, state_json: str) -> Tuple:
    try:
        token, message, success, logged_in_username = await api.login_api_call(username, password, new_api_key)
        
        if not success:
            logger.warning(f"Login failed: {message}")
            return (state_json, True, False, False, message, [], "", "", "", [])
        
        logger.info(f"Login successful for user '{logged_in_username}'")
        state = State.from_json(state_json)
        state.update(token=token, username=logged_in_username)
        
        projects = await api.list_projects(token)
        
        if not projects:
            logger.info(f"No projects found for user '{logged_in_username}'")
            return (state.to_json(), False, True, False, "Login successful. Please create a new project.", [], "", "", "", [])
        
        most_recent_project = projects[0]["name"]
        logger.info(f"Projects found for user '{logged_in_username}'. Most recent: '{most_recent_project}'")
        
        state.update(project=most_recent_project)
        
        return (state.to_json(), False, False, True, message, [p["name"] for p in projects], f"## Current Project: {most_recent_project}", "", "", [])
    
    except Exception as e:
        logger.error(f"Login error: {str(e)}")
        return (state_json, True, False, False, str(e), [], "", "", "", [])

async def handle_registration(username: str, password: str, api_key: str) -> str:
    if not username or not password or not api_key:
        return "All fields are required."
    
    result = await api.register_api_call(username, password, api_key)
    if result.success:
        return "Registration successful. Please log in."
    else:
        return f"Registration failed: {result.error}"

async def create_new_project(state_json: str, new_project_name: str) -> Tuple[str, str, List[str]]:
    state = State.from_json(state_json)
    try:
        create_result = await api.create_project(state.token, new_project_name)
        
        # Update the state with the new project
        state.update(project=new_project_name)
        
        message = f"Project '{new_project_name}' created and activated successfully"
        
        # Update project list
        projects = await api.list_projects(state.token)
        project_names = [p["name"] for p in projects]
        
        return message, state.to_json(), project_names
    except api.APIError as e:
        if "Project already exists" in str(e):
            return f"Error: A project named '{new_project_name}' already exists. Please choose a different name.", state.to_json(), []
        else:
            logger.error(f"Error in create_new_project: {str(e)}")
            return f"Error: {str(e)}", state.to_json(), []
    except Exception as e:
        logger.error(f"Unexpected error in create_new_project: {str(e)}")
        return f"An unexpected error occurred: {str(e)}", state.to_json(), []


async def project_action_handler(action: str, new_project_name: str, existing_project: str) -> Tuple[str, str]:
    if action == CREATE_NEW_PROJECT:
        if not new_project_name:
            return "Project name cannot be empty", ""
        return "", new_project_name
    else:
        return "", existing_project


async def proceed_with_project(state_json: str, selected_project: str) -> Tuple[str, bool, bool, str, str, str, str, List[str]]:
    state = State.from_json(state_json)
    if not selected_project:
        return "No project selected", True, False, state.to_json(), "", "", "", []
    
    state.update(project=selected_project)
    project_visible = True
    llm_visible = True
    try:
        files = await api.list_files(state.token, selected_project)
        main_files = "\n".join(files.get("main", []))
        temp_files = "\n".join(files.get("temp", []))
        all_files = files.get("main", []) + files.get("temp", [])
        return f"Project '{selected_project}' selected", project_visible, llm_visible, state.to_json(), selected_project, main_files, temp_files, all_files
    except Exception as e:
        logger.error(f"Error in proceed_with_project: {str(e)}")
        return f"Error: {str(e)}", project_visible, llm_visible, state.to_json(), selected_project, "", "", []


async def update_project_lists(state_json: str) -> Tuple[List[str], List[str]]:
    try:
        state_dict = json.loads(state_json)
        token = state_dict.get('token', '')
        
        if not token:
            raise api.AuthenticationError("No token found in state")
        
        projects = await api.list_projects(token)
        project_names = [p["name"] for p in projects]
        return project_names, project_names
    except json.JSONDecodeError:
        logger.error("Invalid JSON string for state")
        return [], []
    except api.AuthenticationError as e:
        logger.error(f"Authentication error: {str(e)}")
        return [], []
    except Exception as e:
        logger.error(f"Error updating project lists: {str(e)}")
        return [], []

async def upload_and_update(file: gr.File, state: State) -> Tuple[str, str, str, List[str]]:
    try:
        if not state.token or not state.project:
            logger.warning("Missing token or project name in state during file upload")
            return "Upload failed: No active project or session", "", "", []

        if file.size > MAX_UPLOAD_SIZE:
            return f"File is too big. Maximum allowed size is {MAX_UPLOAD_SIZE / (1024 * 1024):.2f} MB.", "", "", []

        if file.type not in ALLOWED_FILE_TYPES:
            return "Invalid file type. Only text files, PDFs, JSONs, and XMLs are allowed.", "", "", []

        upload_result = await api.upload_file(state.token, state.project, file.name)
        
        if upload_result.get("status") == "error":
            return upload_result.get("message", "Upload failed"), "", "", []

        files = await api.list_files(state.token, state.project)
        
        main_files = "\n".join(files.get("main", []))
        temp_files = "\n".join(files.get("temp", []))
        all_files = files.get("main", []) + files.get("temp", [])
        
        return f"File '{file.name}' uploaded successfully", main_files, temp_files, all_files
    except Exception as e:
        logger.error(f"Error in upload_and_update: {str(e)}")
        return f"Upload failed: {str(e)}", "", "", []

async def update_project_selection(project_name: str, state: State) -> Tuple[str, str, str, str, List[str]]:
    try:
        if not state.token:
            logger.warning("No token found in state during project selection")
            return "", state.to_json(), "", "", []
        
        state.update(project=project_name)
        
        files = await api.list_files(state.token, project_name)
        
        main_files = "\n".join(files.get("main", []))
        temp_files = "\n".join(files.get("temp", []))
        all_files = files.get("main", []) + files.get("temp", [])
        
        return f"## Current Project: {project_name}", state.to_json(), main_files, temp_files, all_files
    except Exception as e:
        logger.error(f"Error in update_project_selection: {str(e)}")
        return "", state.to_json(), "", "", []

async def send_message(message: str, chat_history: List[Dict[str, str]], state: State) -> Tuple[List[Dict[str, str]], str]:
    try:
        state.add_chat_message("user", message)
        response = await api.send_message_to_llm(state.token, state.project, message)
        state.add_chat_message("assistant", response)
        return state.chat_history, ""
    except Exception as e:
        logger.error(f"Error in send_message: {str(e)}")
        return chat_history, f"Error: {str(e)}"

def switch_to_project_tab():
    return PROJECT_TAB, True, False

async def check_and_update_token(state: State) -> Tuple[str, bool, bool, bool]:
    try:
        state_dict = json.loads(state)
        token = state_dict.get('token', '')
        
        if not token:
            logger.info("No token found in state, showing login tab")
            return state, True, False, False
        
        is_valid = await api.validate_token(token)
        
        if is_valid:
            logger.info("Token validated successfully")
            return state, False, True, True
        else:
            logger.warning("Token validation failed")
            state_dict['token'] = ''
            return json.dumps(state_dict), True, False, False
    except Exception as e:
        logger.error(f"Error in check_and_update_token: {str(e)}")
        return state, True, False, False
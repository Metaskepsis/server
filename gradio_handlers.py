import gradio as gr
import mimetypes
from gradio_state_config import *
import gradio_calls as api
import logging
from typing import Dict, List, Tuple
import json

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def handle_login(username: str, password: str, new_api_key: str, state_json: str) -> Tuple[str, gr.update, gr.update, gr.update, str, gr.update, gr.update, str, str, gr.update]:
    try:
        token, message, success, logged_in_username = await api.login_api_call(username, password, new_api_key)
        
        if not success:
            logger.warning(f"Login failed: {message}")
            return (state_json, gr.update(visible=True), gr.update(visible=False), gr.update(visible=False), message, gr.update(choices=[]), gr.update(value=""), "", "", gr.update(choices=[]))
        
        logger.info(f"Login successful for user '{logged_in_username}'")
        state = State.from_json(state_json)
        state.update(token=token, username=logged_in_username)
        
        projects = await api.list_projects(token)
        
        if not projects:
            logger.info(f"No projects found for user '{logged_in_username}'")
            return (state.to_json(), gr.update(visible=False), gr.update(visible=True), gr.update(visible=False), "Login successful. Please create a new project.", gr.update(choices=[]), gr.update(value=""), "", "", gr.update(choices=[]))
        
        most_recent_project = projects[0]["name"]
        logger.info(f"Projects found for user '{logged_in_username}'. Most recent: '{most_recent_project}'")
        
        state.update(project=most_recent_project)
        
        return (state.to_json(), gr.update(visible=False), gr.update(visible=False), gr.update(visible=True), message, gr.update(choices=[p["name"] for p in projects]), gr.update(value=f"## Current Project: {most_recent_project}"), "", "", gr.update(choices=[]))
    
    except Exception as e:
        logger.error(f"Login error: {str(e)}")
        return (state_json, gr.update(visible=True), gr.update(visible=False), gr.update(visible=False), str(e), gr.update(choices=[]), gr.update(value=""), "", "", gr.update(choices=[]))

async def handle_registration(username: str, password: str, api_key: str) -> str:
    if not username or not password or not api_key:
        return "All fields are required."
    
    result = await api.register_api_call(username, password, api_key)
    if result.success:
        return "Registration successful. Please log in."
    else:
        return f"Registration failed: {result.error}"

async def create_new_project(new_project_name: str, state_json: str) -> Tuple[str, str, gr.update, gr.update]:
    try:
        state = State.from_json(state_json)
        create_result = await api.create_project(state.token, new_project_name)
        
        # Fetch the updated list of projects
        projects = await api.list_projects(state.token)
        project_names = [p["name"] for p in projects]
        
        message = f"Project '{new_project_name}' created successfully. Please select it from the dropdown and click Proceed."
        return message, state.to_json(), gr.update(choices=project_names, value=""), gr.update(choices=project_names, value="")
    except json.JSONDecodeError:
        logger.error(f"Invalid state JSON: {state_json}")
        return "Error: Invalid state", state_json, gr.update(), gr.update()
    except Exception as e:
        logger.error(f"Error in create_new_project: {str(e)}")
        return f"Error: {str(e)}", state_json, gr.update(), gr.update()

async def project_action_handler(action: str, new_project_name: str, existing_project: str) -> Tuple[str, str]:
    if action == CREATE_NEW_PROJECT:
        if not new_project_name:
            return "Project name cannot be empty", ""
        return "", new_project_name
    else:
        return "", existing_project


async def upload_and_update(file: gr.File, state_json: str) -> Tuple[str, str, str, gr.update]:
    try:
        state = State.from_json(state_json)
        
        if not state.token or not state.project:
            logger.warning("Missing token or project name in state during file upload")
            return "Upload failed: No active project or session", "", "", gr.update(choices=[])

        if file is None or not file.name:
            return "No file selected for upload", "", "", gr.update(choices=[])

        file_path = file.name

        # Check file size
        file_size = os.path.getsize(file_path)
        if file_size > MAX_UPLOAD_SIZE:
            return f"File is too big. Maximum allowed size is {MAX_UPLOAD_SIZE / (1024 * 1024):.2f} MB.", "", "", gr.update(choices=[])

        # Check file type
        file_type = mimetypes.guess_type(file_path)[0]
        if file_type not in ALLOWED_FILE_TYPES:
            return "Invalid file type. Only text files, PDFs, JSONs, and XMLs are allowed.", "", "", gr.update(choices=[])

        upload_result = await api.upload_file(state.token, state.project, file_path)
        
        if upload_result.get("status") == "error":
            return upload_result.get("message", "Upload failed"), "", "", gr.update(choices=[])

        files = await api.list_files(state.token, state.project)
        
        main_files = "\n".join(files.get("main", []))
        temp_files = [[file] for file in files.get("temp", [])]
        all_files = files.get("main", []) + files.get("temp", [])
        
        return f"File '{os.path.basename(file_path)}' uploaded successfully", main_files, temp_files, gr.update(choices=all_files)
    except Exception as e:
        logger.error(f"Error in upload_and_update: {str(e)}")
        return f"Upload failed: {str(e)}", "", [[]], gr.update(choices=[])

async def update_project_selection(project_name: str, state_json: str) -> Tuple[gr.update, str, str, str, gr.update]:
    try:
        state = State.from_json(state_json)
        if not state.token:
            logger.warning("No token found in state during project selection")
            return gr.update(value=""), state_json, "", "", gr.update(choices=[])
        
        state.update(project=project_name)
        
        files = await api.list_files(state.token, project_name)
        
        main_files = "\n".join(files.get("main", []))
        temp_files = "\n".join(files.get("temp", []))
        all_files = files.get("main", []) + files.get("temp", [])
        
        return gr.update(value=f"## Current Project: {project_name}"), state.to_json(), main_files, temp_files, gr.update(choices=all_files)
    except json.JSONDecodeError:
        logger.error(f"Invalid state JSON: {state_json}")
        return gr.update(value=""), state_json, "", "", gr.update(choices=[])
    except Exception as e:
        logger.error(f"Error in update_project_selection: {str(e)}")
        return gr.update(value=""), state_json, "", "", gr.update(choices=[])

async def send_message(message: str, chat_history: List[Dict[str, str]], state: State) -> Tuple[List[Dict[str, str]], str]:
    try:
        state.add_chat_message("user", message)
        response = await api.send_message_to_llm(state.token, state.project, message)
        state.add_chat_message("assistant", response)
        return state.chat_history, ""
    except Exception as e:
        logger.error(f"Error in send_message: {str(e)}")
        return chat_history, f"Error: {str(e)}"


async def handle_project_selection(action: str, new_project_name: str, existing_project: str, state_json: str) -> Tuple[str, str, gr.update, gr.update, bool]:
    try:
        state = State.from_json(state_json)
        if action == CREATE_NEW_PROJECT:
            message, state_json, project_dropdown, llm_selector = await create_new_project(new_project_name, state_json)
            return message, state_json, project_dropdown, llm_selector, False
        elif action == CHOOSE_EXISTING_PROJECT:
            if not existing_project:
                return "Please select a project", state_json, gr.update(), gr.update(), False
            state.update(project=existing_project)
            return f"Selected project: {existing_project}", state.to_json(), gr.update(), gr.update(value=existing_project), True
        else:
            return "Invalid action", state_json, gr.update(), gr.update(), False
    except json.JSONDecodeError:
        logger.error(f"Invalid state JSON: {state_json}")
        return "Error: Invalid state", state_json, gr.update(), gr.update(), False
    except Exception as e:
        logger.error(f"Error in handle_project_selection: {str(e)}")
        return f"Error: {str(e)}", state_json, gr.update(), gr.update(), False
    


async def update_project_dropdown(state_json: str) -> gr.update:
    try:
        state = State.from_json(state_json)
        projects = await api.list_projects(state.token)
        project_names = [p["name"] for p in projects]
        return gr.update(choices=project_names)
    except json.JSONDecodeError:
        logger.error(f"Invalid state JSON: {state_json}")
        return gr.update()
    except Exception as e:
        logger.error(f"Error updating project dropdown: {str(e)}")
        return gr.update()
    
def conditional_tab_switch(switch_to_llm: bool):
    if switch_to_llm:
        return gr.update(visible=False), gr.update(visible=False), gr.update(visible=True)
    else:
        return gr.update(visible=False), gr.update(visible=True), gr.update(visible=False)

def switch_to_project_tab():
    return (
        gr.update(visible=False),  # login_tab
        gr.update(visible=True),   # project_tab
        gr.update(visible=False),  # llm_tab
        gr.update(value=CREATE_NEW_PROJECT),  # project_action
        gr.update(value=""),  # new_project_name
        gr.update(value="")   # project_dropdown
    )






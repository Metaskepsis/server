import gradio as gr
from gradio_state_config import State, LOGIN_TAB, PROJECT_TAB, LLM_TAB, CREATE_NEW_PROJECT, CHOOSE_EXISTING_PROJECT, MAX_UPLOAD_SIZE, ALLOWED_FILE_TYPES
import gradio_calls as api
import logging
from typing import Dict, List, Tuple
import json
import os

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def handle_login(username: str, password: str, new_api_key: str, state: State) -> Tuple:
    try:
        token, message, success, logged_in_username = await api.login_api_call(username, password, new_api_key)
        
        if not success:
            logger.warning(f"Login failed: {message}")
            return (
                state.to_json(),
                gr.update(visible=True),        # login_content
                gr.update(visible=False),       # project_content
                gr.update(visible=False),       # llm_content
                message,                        # login_components['message']
                gr.update(choices=[]),          # project_components['project_dropdown']
                gr.update(),                    # llm_components['project_name']
                "",                             # llm_components['main_files_output']
                "",                             # llm_components['temp_files_output']
                gr.update(choices=[])           # llm_components['file_selector']
            )
        
        logger.info(f"Login successful for user '{logged_in_username}'")
        state.update(token=token, username=logged_in_username)
        
        projects = await api.list_projects(token)
        
        if not projects:
            logger.info(f"No projects found for user '{logged_in_username}'")
            return (
                state.to_json(),
                gr.update(visible=False),                          # login_content
                gr.update(visible=True),                           # project_content
                gr.update(visible=False),                          # llm_content
                message,                                           # login_components['message']
                gr.update(choices=[]),                             # project_components['project_dropdown']
                gr.update(),                                       # llm_components['project_name']
                "",                                                # llm_components['main_files_output']
                "",                                                # llm_components['temp_files_output']
                gr.update(choices=[])                              # llm_components['file_selector']
            )
        
        most_recent_project = projects[0]["name"]
        logger.info(f"Projects found for user '{logged_in_username}'. Most recent: '{most_recent_project}'")
        
        state.update(project=most_recent_project)
        
        return (
            state.to_json(),
            gr.update(visible=False),                          # login_content
            gr.update(visible=False),                          # project_content
            gr.update(visible=True),                           # llm_content
            message,                                           # login_components['message']
            gr.update(choices=[p["name"] for p in projects], value=most_recent_project),  # project_components['project_dropdown']
            gr.update(value=f"## Current Project: {most_recent_project}"),  # llm_components['project_name']
            "",                                                # llm_components['main_files_output']
            "",                                                # llm_components['temp_files_output']
            gr.update(choices=[])                              # llm_components['file_selector']
        )
    
    except Exception as e:
        logger.error(f"Login error: {str(e)}")
        return (
            state.to_json(),
            gr.update(visible=True),        # login_content
            gr.update(visible=False),       # project_content
            gr.update(visible=False),       # llm_content
            str(e),                         # login_components['message']
            gr.update(choices=[]),          # project_components['project_dropdown']
            gr.update(),                    # llm_components['project_name']
            "",                             # llm_components['main_files_output']
            "",                             # llm_components['temp_files_output']
            gr.update(choices=[])           # llm_components['file_selector']
        )

async def handle_registration(username: str, password: str, api_key: str) -> str:
    if not username or not password or not api_key:
        return "All fields are required."
    
    result = await api.register_api_call(username, password, api_key)
    if result.success:
        return "Registration successful. Please log in."
    else:
        return f"Registration failed: {result.error}"

async def project_action_handler(action: str, new_project_name: str, existing_project: str) -> Tuple[str, str]:
    if action == CREATE_NEW_PROJECT:
        if not new_project_name:
            return "Project name cannot be empty", ""
        return "", new_project_name
    else:
        return "", existing_project

async def proceed_with_project(state: State, project: str) -> Tuple:
    if not project:
        return "No project selected", gr.update(visible=True), gr.update(visible=False), state.to_json(), gr.update(), "", "", gr.update(choices=[])
    
    try:
        state_dict = json.loads(state)
        token = state_dict.get('token', '')
        
        files = await api.list_files(token, project)
        main_files = "\n".join(files.get("main", []))
        temp_files = "\n".join(files.get("temp", []))
        
        state_dict['project'] = project
        new_state = json.dumps(state_dict)
        
        return (
            f"Proceeding with project: {project}",
            gr.update(visible=False),
            gr.update(visible=True),
            new_state,
            gr.update(value=f"## Current Project: {project}"),
            main_files,
            temp_files,
            gr.update(choices=files.get("main", []) + files.get("temp", [])),
        )
    except Exception as e:
        logger.error(f"Error proceeding with project: {str(e)}")
        return f"Error: {str(e)}", gr.update(visible=True), gr.update(visible=False), state, gr.update(), "", "", gr.update(choices=[])

async def update_project_lists(state_json: str) -> Tuple[gr.update, gr.update]:
    try:
        state_dict = json.loads(state_json)
        token = state_dict.get('token', '')
        
        if not token:
            raise api.AuthenticationError("No token found in state")
        
        projects = await api.list_projects(token)
        project_names = [p["name"] for p in projects]
        return (
            gr.update(choices=project_names, value=project_names[0] if project_names else None),
            gr.update(choices=project_names, value=project_names[0] if project_names else None),
        )
    except json.JSONDecodeError:
        logger.error("Invalid JSON string for state")
        return gr.update(choices=[]), gr.update(choices=[])
    except api.AuthenticationError as e:
        logger.error(f"Authentication error: {str(e)}")
        return gr.update(choices=[]), gr.update(choices=[])
    except Exception as e:
        logger.error(f"Error updating project lists: {str(e)}")
        return gr.update(choices=[]), gr.update(choices=[])

async def upload_and_update(file: gr.File, state: State) -> Tuple[str, str, str, gr.update]:
    try:
        if not state.token or not state.project:
            logger.warning("Missing token or project name in state during file upload")
            return "Upload failed: No active project or session", "", "", gr.update(choices=[])

        # Check file size
        if file.size > MAX_UPLOAD_SIZE:
            return f"File is too big. Maximum allowed size is {MAX_UPLOAD_SIZE / (1024 * 1024):.2f} MB.", "", "", gr.update(choices=[])

        # Check file type
        if file.type not in ALLOWED_FILE_TYPES:
            return "Invalid file type. Only text files, PDFs, JSONs, and XMLs are allowed.", "", "", gr.update(choices=[])

        # Upload the file
        upload_result = await api.upload_file(state.token, state.project, file.name)
        
        if upload_result.get("status") == "error":
            return upload_result.get("message", "Upload failed"), "", "", gr.update(choices=[])

        # Fetch updated file lists
        files = await api.list_files(state.token, state.project)
        
        main_files = "\n".join(files.get("main", []))
        temp_files = "\n".join(files.get("temp", []))
        all_files = files.get("main", []) + files.get("temp", [])
        
        return (
            f"File '{file.name}' uploaded successfully",  # upload_message
            main_files,  # main_files_output
            temp_files,  # temp_files_output
            gr.update(choices=all_files)  # file_selector
        )
    except Exception as e:
        logger.error(f"Error in upload_and_update: {str(e)}")
        return f"Upload failed: {str(e)}", "", "", gr.update(choices=[])

async def update_project_selection(project_name: str, state: State) -> Tuple[gr.update, str, str, str, gr.update]:
    try:
        if not state.token:
            logger.warning("No token found in state during project selection")
            return gr.update(), state.to_json(), "", "", gr.update(choices=[])
        
        # Update the current project in the state
        state.update(project=project_name)
        
        # Fetch files for the selected project
        files = await api.list_files(state.token, project_name)
        
        main_files = "\n".join(files.get("main", []))
        temp_files = "\n".join(files.get("temp", []))
        all_files = files.get("main", []) + files.get("temp", [])
        
        return (
            gr.update(value=f"## Current Project: {project_name}"),  # project_name
            state.to_json(),  # updated state
            main_files,  # main_files_output
            temp_files,  # temp_files_output
            gr.update(choices=all_files)  # file_selector
        )
    except Exception as e:
        logger.error(f"Error in update_project_selection: {str(e)}")
        return gr.update(), state.to_json(), "", "", gr.update(choices=[])

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
    return gr.update(selected=PROJECT_TAB), gr.update(visible=True), gr.update(visible=False)

async def check_and_update_token(state: State) -> Tuple[str, gr.update, gr.update, gr.update]:
    try:
        if not state.token:
            logger.warning("No token found in state during token validation")
            state.clear()
            return state.to_json(), gr.update(visible=True), gr.update(visible=False), gr.update(visible=False)
        
        is_valid = await api.validate_token(state.token)
        
        if is_valid:
            logger.info("Token validated successfully")
            return state.to_json(), gr.update(visible=False), gr.update(visible=True), gr.update(visible=True)
        else:
            logger.warning("Token validation failed")
            state.clear()
            return state.to_json(), gr.update(visible=True), gr.update(visible=False), gr.update(visible=False)
    except Exception as e:
        logger.error(f"Error in check_and_update_token: {str(e)}")
        state.clear()
        return state.to_json(), gr.update(visible=True), gr.update(visible=False), gr.update(visible=False)
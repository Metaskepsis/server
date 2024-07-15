# handlers.py

import gradio as gr
import re
from typing import Dict, List, Tuple, Optional
from gradio_calls import *
import logging
import aiohttp

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def handle_login(username: str, password: str, new_api_key: str) -> Tuple:
    try:
        token, message, success, logged_in_username = await login_api_call(username, password, new_api_key)
        
        if not success:
            logger.warning(f"Login failed: {message}")
            return ("", "", gr.update(visible=True), gr.update(visible=False), gr.update(visible=False), message, gr.update(choices=[]), "", gr.update(), "", "", gr.update(choices=[]))
        
        logger.info(f"Login successful for user '{logged_in_username}' with token {token[:5]}...")
        
        try:
            projects = await list_projects(token)
            
            if not projects:
                logger.info(f"No projects found for user '{logged_in_username}'")
                return (token, logged_in_username, gr.update(visible=False), gr.update(visible=True), gr.update(visible=False), message, gr.update(choices=[]), "", gr.update(), "", "", gr.update(choices=[]))
            
            most_recent_project = projects[0]["name"]
            logger.info(f"Projects found for user '{logged_in_username}'. Most recent: '{most_recent_project}'")
            
            return (
                token,
                logged_in_username,
                gr.update(visible=False),
                gr.update(visible=False),
                gr.update(visible=True),
                message,
                gr.update(choices=[p["name"] for p in projects], value=most_recent_project),
                most_recent_project,
                gr.update(value=f"## Current Project: {most_recent_project}"),
                "",
                "",
                gr.update(choices=[])
            )
        
        except Exception as e:
            logger.error(f"Error fetching projects for user '{logged_in_username}': {str(e)}")
            return (token, logged_in_username, gr.update(visible=False), gr.update(visible=True), gr.update(visible=False), f"{message} (Error fetching projects)", gr.update(choices=[]), "", gr.update(), "", "", gr.update(choices=[]))
    
    except Exception as e:
        logger.error(f"Login error: {str(e)}")
        return ("", "", gr.update(visible=True), gr.update(visible=False), gr.update(visible=False), str(e), gr.update(choices=[]), "", gr.update(), "", "", gr.update(choices=[]))

def update_visibility(login_visible: bool, project_visible: bool, llm_visible: bool) -> Tuple[gr.update, gr.update, gr.update]:
    """Update the visibility of main interface tabs."""
    return tuple(gr.update(visible=v) for v in (login_visible, project_visible, llm_visible))

async def validate_token(token: str) -> bool:
    """Validate the token by making a test request."""
    try:
        await make_api_request('GET', 'users/me', token)
        return True
    except aiohttp.ClientResponseError as e:
        if e.status == 401:
            return False
        else:
            raise
    except Exception:
        return False

async def handle_registration(username: str, password: str, api_key: str) -> str:
    if not username or not password or not api_key:
        return "All fields are required."
    if not 6 <= len(username) <= 20:
        return "Username must be between 6 and 20 characters."
    if not re.match(r'^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&])[A-Za-z\d@$!%*?&]{8,}$', password):
        return "Password must be at least 8 characters long, contain uppercase and lowercase letters, a digit, and a special character."

    result = await register_api_call(username, password, api_key)
    if result.success:
        return "Registration successful. Please log in."
    else:
        return f"Registration failed: {result.error}"

async def upload_and_update(file: gr.File, state: Dict[str, str]):
    if not state['project']:
        return "No project selected", "", "", gr.update(choices=[])

    if file is None:
        return "No file selected", "", "", gr.update(choices=[])

    token = state['token']
    project_name = state['project']

    try:
        files = {'file': (file.name, file.read(), file.type)}
        response = await make_api_request('POST', f'upload/{project_name}', token=token, files=files)
        
        if isinstance(response, dict) and "message" in response:
            message = response["message"]
            files = await update_file_lists(token, project_name)
            main_files = "\n".join(files.get("main", []))
            temp_files = "\n".join(files.get("temp", []))
            file_choices = files.get("main", []) + files.get("temp", [])
            return message, main_files, temp_files, gr.update(choices=file_choices)
        else:
            return "Upload failed: Unexpected response from server", "", "", gr.update(choices=[])
    except AuthenticationError:
        return "Authentication failed. Please log in again.", "", "", gr.update(choices=[])
    except APIError as e:
        return f"Upload failed: {str(e)}", "", "", gr.update(choices=[])
    except Exception as e:
        return f"An unexpected error occurred: {str(e)}", "", "", gr.update(choices=[])

async def send_message(message: str, history: List[Tuple[str, str]]) -> Tuple[List[Tuple[str, str]], str]:
    # This is a placeholder. Implement actual LLM integration here.
    history.append((message, "This is a placeholder response. The actual LLM integration is not implemented yet."))
    return history, ""

def switch_to_project_tab():
    return gr.update(selected="project"), gr.update(visible=True), gr.update(visible=False)        

def project_action_handler(action: str, new_project_name: str, existing_project: str) -> Tuple[str, str]:
    if action == "Create New Project":
        if not new_project_name:
            return "Project name cannot be empty", ""
        if not re.match(r'^[a-zA-Z0-9_-]+$', new_project_name):
            return "Invalid project name. Use only letters, numbers, underscores, and hyphens.", ""
        return "", new_project_name
    else:
        return "", existing_project

async def proceed_with_project(token: str, project: str) -> Tuple:
    if not project:
        return "No project selected", gr.update(visible=True), gr.update(visible=False), project, gr.update(), "", "", gr.update(choices=[])
    
    try:
        projects = await list_projects(token)
        project_names = [p["name"] for p in projects]
        
        files = await list_files(token, project)
        if files is None:
            files = {"main": [], "temp": []}
        main_files = "\n".join(files.get("main", []))
        temp_files = "\n".join(files.get("temp", []))
        
        return (
            f"Proceeding with project: {project}",
            gr.update(visible=False),
            gr.update(visible=True),
            project,
            gr.update(value=f"## Current Project: {project}"),
            main_files,
            temp_files,
            gr.update(choices=files.get("main", []) + files.get("temp", [])),
        )
    except Exception as e:
        logger.error(f"Error proceeding with project: {str(e)}")
        return f"Error: {str(e)}", gr.update(visible=True), gr.update(visible=False), "", gr.update(), "", "", gr.update(choices=[])

async def update_project_selection(project_name: str, token: str) -> Tuple:
    if project_name:
        try:
            files = await list_files(token, project_name)
            main_files = "\n".join(files.get("main", []))
            temp_files = "\n".join(files.get("temp", []))
            return (
                gr.update(value=f"## Current Project: {project_name}"),
                project_name,
                main_files,
                temp_files,
                gr.update(choices=files.get("main", []) + files.get("temp", []))
            )
        except (AuthenticationError, APIError) as e:
            logger.error(f"Error updating project selection: {str(e)}")
            return (
                gr.update(value="## Current Project: Error"),
                "",
                "",
                "",
                gr.update(choices=[])
            )
    return (
        gr.update(value="## Current Project: None"),
        "",
        "",
        "",
        gr.update(choices=[])
    )

async def update_project_lists(token: str) -> Tuple[gr.update, gr.update]:
    try:
        projects = await list_projects(token)
        project_names = [p["name"] for p in projects]
        return (
            gr.update(choices=project_names, value=project_names[0] if project_names else None),
            gr.update(choices=project_names, value=project_names[0] if project_names else None),
        )
    except AuthenticationError:
        return (
            gr.update(choices=[]),
            gr.update(choices=[]),
        )

async def update_file_lists(token: str, project: str) -> Dict[str, List[str]]:
    logger.info(f"update_file_lists called with token: {token[:5]}... and project: {project}")
    if not token:
        logger.error("Attempted to update file lists without a token")
        return {"main": [], "temp": []}
    if not project:
        logger.warning("Attempted to update file lists with no project selected")
        return {"main": [], "temp": []}
    try:
        logger.info(f"Calling list_files for project '{project}' with token {token[:5]}...")
        files = await list_files(token, project)
        logger.info(f"Files retrieved for project '{project}': {files}")
        return files
    except AuthenticationError:
        logger.error(f"Authentication failed when updating file lists for project '{project}'")
        return {"main": [], "temp": []}
    except Exception as e:
        logger.error(f"Error updating file lists for project '{project}': {str(e)}")
        return {"main": [], "temp": []}

async def check_and_update_token(token: str) -> Tuple[str, gr.update, gr.update, gr.update]:
    if await validate_token(token):
        return token, gr.update(visible=False), gr.update(visible=True), gr.update(visible=True)
    else:
        return "", gr.update(visible=True), gr.update(visible=False), gr.update(visible=False)
import gradio as gr
import mimetypes
from gradio_state_config import *
import gradio_calls as api
import logging
from typing import Dict, List, Tuple
import json
import os
import markdown
import tempfile
import base64
from PIL import Image
import io
import html

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Login Tab Methods
async def handle_login(username: str, password: str, new_api_key: str, state_json: str) -> Tuple[str, gr.update, gr.update, gr.update, str, gr.update, gr.update, str, gr.update]:
    try:
        token, message, success, logged_in_username = await api.login_api_call(username, password, new_api_key)
        
        if not success:
            logger.warning(f"Login failed: {message}")
            return (state_json, gr.update(visible=True), gr.update(visible=False), gr.update(visible=False), message, gr.update(choices=[]), gr.update(value=""), gr.update(choices=[]), gr.update(choices=[]))
        
        logger.info(f"Login successful for user '{logged_in_username}'")
        state = State.from_json(state_json)
        state.update(token=token, username=logged_in_username, selected_file="", project_creation_chat_history=[])
        
        projects = await api.list_projects(token)
        
        if not projects:
            logger.info(f"No projects found for user '{logged_in_username}'")
            return (state.to_json(), gr.update(visible=False), gr.update(visible=True), gr.update(visible=False), "Login successful. Please create a new project.", gr.update(choices=[]), gr.update(value=""), gr.update(choices=[]), gr.update(choices=[]))
        
        most_recent_project = projects[0]["name"]
        project_names = [p["name"] for p in projects]
        logger.info(f"Projects found for user '{logged_in_username}'. Most recent: '{most_recent_project}'")
        
        state.update(project=most_recent_project)
        
        return (state.to_json(), gr.update(visible=False), gr.update(visible=False), gr.update(visible=True), message, gr.update(choices=project_names, value=most_recent_project), gr.update(value=f"## Current Project: {most_recent_project}"), gr.update(choices=[]), gr.update(choices=project_names, value=most_recent_project))
    
    except Exception as e:
        logger.error(f"Login error: {str(e)}")
        return (state_json, gr.update(visible=True), gr.update(visible=False), gr.update(visible=False), str(e), gr.update(choices=[]), gr.update(value=""), gr.update(choices=[]), gr.update(choices=[]))

async def handle_registration(username: str, password: str, api_key: str) -> str:
    if not username or not password or not api_key:
        return "All fields are required."
    
    result = await api.register_api_call(username, password, api_key)
    if result.success:
        return "Registration successful. Please log in."
    else:
        return f"Registration failed: {result.error}"

# Project Tab Methods

async def handle_upload_file_button(state_json: str):
    return gr.update(visible=True), gr.update(visible=True)

async def handle_create_empty_project(new_project_name: str, state_json: str) -> Tuple[str, str, gr.update, gr.update]:
    if not new_project_name:
        return "Project name cannot be empty", state_json, gr.update(), gr.update()

    try:
        state = State.from_json(state_json)
        create_result = await api.create_project(state.token, new_project_name)
        
        if "message" in create_result:
            # Project created successfully
            message = create_result["message"]
            
            # Fetch the updated list of projects
            projects = await api.list_projects(state.token)
            project_names = [p["name"] for p in projects]
            
            return message, state.to_json(), gr.update(choices=project_names, value=new_project_name), gr.update(choices=project_names, value=new_project_name)
        else:
            # Unexpected response format
            return f"Unexpected response when creating project", state_json, gr.update(), gr.update()
    except api.APIError as e:
        logger.error(f"Error in handle_create_new_project: {str(e)}")
        return f"Error: {str(e)}", state_json, gr.update(), gr.update()
    except json.JSONDecodeError:
        logger.error(f"Invalid state JSON: {state_json}")
        return "Error: Invalid state", state_json, gr.update(), gr.update()
    except Exception as e:
        logger.error(f"Error in handle_create_new_project: {str(e)}")
        return f"Error: {str(e)}", state_json, gr.update(), gr.update()

async def send_message_project_tab(message: str, chat_history: List[Dict[str, str]], state_json: str) -> Tuple[List[Dict[str, str]], str, str]:
    state = State.from_json(state_json)
    try:
        state.add_chat_message("user", message, is_project_creation=True)
        response = await api.send_message_to_llm(state.token, state.project, message)
        state.add_chat_message("assistant", response, is_project_creation=True)
        return state.project_creation_chat_history, "", state.to_json()
    except Exception as e:
        logger.error(f"Error in send_message_project_tab: {str(e)}")
        return chat_history, f"Error: {str(e)}", state_json

async def handle_answer_questions(state_json: str, new_project_name: str ):
    pass

def handle_proceed_button(state_json: str) -> Tuple[gr.update, gr.update, gr.update, str]:
    try:
        state = State.from_json(state_json)
        if not state.project:
            return gr.update(visible=True), gr.update(visible=True), gr.update(visible=False), "No project selected. Please select a project before proceeding."
        else:
            return gr.update(visible=False), gr.update(visible=False), gr.update(visible=True), ""
    except Exception as e:
        logger.error(f"Error in handle_proceed_button: {str(e)}")
        return gr.update(visible=True), gr.update(visible=True), gr.update(visible=False), f"An error occurred: {str(e)}"



# LLM Tab Methods

    
def handle_file_selection(file_path: str, state_json: str) -> Tuple[str, str]:
    logger.info(f"handle_file_selection called with file_path: {file_path}")
    try:
        state = State.from_json(state_json)
        if not state.token or not state.project:
            return state_json, "No active project or session"

        if file_path is None or file_path.strip() == "":
            state.selected_file = ""
            return state.to_json(), "No file selected"

        file_path = file_path.strip()
        logger.info(f"Stripped file_path: {file_path}")
        
        if file_path.startswith("Main Files:"):
            folder = "main"
            file_name = file_path[len("Main Files:"):].strip()
        elif file_path.startswith("Temp Files:"):
            folder = "temp"
            file_name = file_path[len("Temp Files:"):].strip()
        else:
            if '/' in file_path:
                state.selected_file = file_path
                logger.info(f"File already has a folder, selected_file set to: {state.selected_file}")
                return state.to_json(), f"Selected file: {state.selected_file}"
            else:
                folder = "temp"
                file_name = file_path

        state.selected_file = f"{folder}/{file_name}"
        logger.info(f"Final selected_file: {state.selected_file}")
        return state.to_json(), f"Selected file: {state.selected_file}"
    except Exception as e:
        logger.error(f"Error in handle_file_selection: {str(e)}")
        return state_json, f"Error: {str(e)}"

async def upload_and_update(file: gr.File, state_json: str) -> Tuple[str, gr.update, gr.update]:
    try:
        state = State.from_json(state_json)
        
        if not state.token or not state.project:
            logger.warning("Missing token or project name in state during file upload")
            return "Upload failed: No active project or session", gr.update(value=None), gr.update(choices=[])

        if file is None or not file.name:
            return "No file selected for upload", gr.update(value=None), gr.update(choices=[])

        file_path = file.name

        # Check file size
        file_size = os.path.getsize(file_path)
        if file_size > MAX_UPLOAD_SIZE:
            return f"File is too big. Maximum allowed size is {MAX_UPLOAD_SIZE / (1024 * 1024):.2f} MB.", gr.update(value=None), gr.update(choices=[])

        # Check file type
        file_type = mimetypes.guess_type(file_path)[0]
        if file_type not in ALLOWED_FILE_TYPES:
            return "Invalid file type. Only text files, PDFs, JSONs, and XMLs are allowed.", gr.update(value=None), gr.update(choices=[])

        upload_result = await api.upload_file(state.token, state.project, file_path)
        
        if upload_result.get("status") == "error":
            return upload_result.get("message", "Upload failed"), gr.update(value=None), gr.update(choices=[])

        files = await api.list_files(state.token, state.project)
        all_files = files.get("main", []) + files.get("temp", [])
        
        return f"File '{os.path.basename(file_path)}' uploaded successfully", gr.update(value=None), gr.update(choices=all_files)
    except Exception as e:
        logger.error(f"Error in upload_and_update: {str(e)}")
        files = await api.list_files(state.token, state.project)
        all_files = files.get("main", []) + files.get("temp", [])
        return f"Upload failed: {str(e)}", gr.update(value=None), gr.update(choices=all_files)

async def send_message(message: str, chat_history: List[Dict[str, str]], state: State) -> Tuple[List[Dict[str, str]], str]:
    try:
        state.add_chat_message("user", message)
        response = await api.send_message_to_llm(state.token, state.project, message)
        state.add_chat_message("assistant", response)
        return state.chat_history, ""
    except Exception as e:
        logger.error(f"Error in send_message: {str(e)}")
        return chat_history, f"Error: {str(e)}"


def is_pdf_with_images(content):
    return content.startswith(b'%PDF') and (b'/XObject' in content or b'/Image' in content)

def is_image(content):
    try:
        Image.open(io.BytesIO(content))
        return True
    except IOError:
        return False


async def visualize_file(state_json: str):
    logger.info("Visualize file called")
    try:
        state = State.from_json(state_json)
    except json.JSONDecodeError as e:
        logger.error(f"Error decoding state JSON: {e}")
        return gr.update(value='<p>Error: Invalid state information. Please try reloading the page.</p>')
    logger.info(f"State selected_file: '{state.selected_file}'")
    
    if not state.selected_file or not state.project:
        logger.warning("No file selected in state or no active project.")
        return gr.update(value='<p>No file selected in the current project. Please choose a file to visualize.</p>')
    try:
        logger.info(f"Attempting to get file content for '{state.selected_file}' in project '{state.project}'")
        response = await api.get_file_content(state.token, state.project, state.selected_file)
        logger.info(f"Response received for file: {response['name']}")
        content = response["content"]
        
        # Infer file type from content
        if content.startswith(b'%PDF'):
            file_type = "application/pdf"
        elif is_image(content):
            file_type = "image"
        else:
            file_type = "text"
        
        # Wrapper for scrollable content
        scroll_wrapper = '<div style="max-height: 500px; overflow-y: auto; border: 1px solid #ccc; padding: 10px;">{}</div>'
        
        if file_type == "image":
            logger.info("Preparing image content for display")
            img_data = base64.b64encode(content).decode('utf-8')
            img_html = f'<img src="data:image/png;base64,{img_data}" alt="{state.selected_file}" style="max-width:100%; height:auto;">'
            return gr.update(value=scroll_wrapper.format(img_html))
        
        elif file_type == "application/pdf":
            logger.info("Preparing PDF content for display")
            # Create a temporary file to store the PDF
            with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_pdf:
                temp_pdf.write(content)
                temp_pdf_path = temp_pdf.name

            # Use pdf2image to convert PDF to images
            from pdf2image import convert_from_path
            images = convert_from_path(temp_pdf_path, size=(800, None))

            # Create HTML to display PDF images
            pdf_html = ""
            for i, image in enumerate(images):
                with tempfile.NamedTemporaryFile(delete=False, suffix='.png') as temp_img:
                    image.save(temp_img, format='PNG')
                    img_data = base64.b64encode(open(temp_img.name, 'rb').read()).decode('utf-8')
                    pdf_html += f'<img src="data:image/png;base64,{img_data}" style="width:100%; margin-bottom:10px;">'
                os.unlink(temp_img.name)  # Remove temporary image file

            os.unlink(temp_pdf_path)  # Remove temporary PDF file

            if is_pdf_with_images(content):
                pdf_html = f"<p>This PDF contains images.</p>{pdf_html}"
            else:
                pdf_html = f"<p>This is a simple PDF without images.</p>{pdf_html}"

            return gr.update(value=scroll_wrapper.format(pdf_html))
        else:
            logger.info("Preparing text content for display")
            file_extension = os.path.splitext(state.selected_file)[1].lower()
            if file_extension in ['.md', '.markdown']:
                # Convert markdown to HTML
                html_content = markdown.markdown(content.decode('utf-8'))
                return gr.update(value=scroll_wrapper.format(html_content))
            else:
                # Wrap plain text in pre tag to preserve formatting
                text_content = f'<pre>{html.escape(content.decode("utf-8"))}</pre>'
                return gr.update(value=scroll_wrapper.format(text_content))
    except Exception as e:
        logger.error(f"Error visualizing file: {str(e)}")
        return gr.update(value=f'<p style="color: red;">Error visualizing file: {str(e)}</p>')

def switch_to_project_tab():
    return (
        gr.update(visible=False),  # login_tab
        gr.update(visible=True),   # project_tab
        gr.update(visible=False),  # llm_tab
        )

# Shared Methods
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
    
async def update_project_and_files(project_name: str, state_json: str) -> Tuple[str, List[str], str, str]:
    try:
        state = State.from_json(state_json)
        if not state.token:
            logger.warning("No token found in state during project selection")
            return state_json, [], "", "No active session"

        state.update(project=project_name)
        
        files = await api.list_files(state.token, project_name)
        
        main_files = files.get("main", [])
        temp_files = files.get("temp", [])
        
        # Create a structured list of files
        file_structure = ["Main Files:"] + [f"  {file}" for file in main_files]
        if temp_files:
            file_structure += ["Temp Files:"] + [f"  {file}" for file in temp_files]
        
        # Update the selected file
        all_files = main_files + temp_files
        if all_files:
            # Select the most recent file
            most_recent_file = all_files[-1]
            folder = "main" if most_recent_file in main_files else "temp"
            state.selected_file = f"{folder}/{most_recent_file}"
        else:
            state.selected_file = ""
            file_structure = []  # Empty list if there are no files

        selected_file_message = f"Selected file: {state.selected_file}" if state.selected_file else "No files in the project"
        
        return state.to_json(), file_structure, state.selected_file, selected_file_message
    except Exception as e:
        logger.error(f"Error in update_project_and_files: {str(e)}")
        return state_json, [], "", f"Error: {str(e)}"

async def handle_project_selection(existing_project: str, state_json: str) -> Tuple[str, str, gr.update, gr.update, gr.update, str]:
    try:
        if not existing_project:
            return "Please select a project", state_json, gr.update(), gr.update(), gr.update(visible=True), ""
        
        state_json, _ , _ , message = await update_project_and_files(existing_project, state_json)
        
        return (
            f"Selected project: {existing_project}. {message}",state_json,gr.update(value=existing_project))
    except Exception as e:
        logger.error(f"Error in handle_project_selection: {str(e)}")
        return f"Error: {str(e)}", state_json, gr.update(visible=True)
    
async def update_project_selection(project_name: str, state_json: str) -> Tuple[gr.update, str, gr.update, str, gr.update]:
    try:
        state = State.from_json(state_json)
        state_json, file_structure, selected_file, message = await update_project_and_files(project_name, state_json)
        
        # Fetch the updated list of projects
        projects = await api.list_projects(state.token)
        project_names = [p["name"] for p in projects]
        
        return (
            gr.update(value=f"## Current Project: {project_name}"),
            state_json,
            gr.update(choices=file_structure, value=selected_file if selected_file else None),
            message,
            gr.update(choices=project_names, value=project_name)  # Update project selector
        )
    except Exception as e:
        logger.error(f"Error in update_project_selection: {str(e)}")
        return (
            gr.update(value="## Current Project: None"),
            state_json,
            gr.update(choices=[], value=None),
            f"Error: {str(e)}",
            gr.update(choices=[], value=None)
        )
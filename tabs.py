# tabs.py

import gradio as gr
import re
from typing import Dict, List, Tuple, Callable
from gradio_util import (
    login_api_call, register_api_call, list_projects, list_files, upload_file,
    APIError, AuthenticationError, APIResponse
)

import gradio as gr
from typing import Dict, Tuple
import re
from gradio_util import login_api_call, register_api_call

def create_login_tab() -> Dict:
    """
    Create and return the login/register tab components.
    
    Returns:
        dict: A dictionary containing all the Gradio components for the login/register tab
    """
    with gr.Column():
        gr.Markdown("## Welcome to the Application")
        
        # Radio button to switch between login and register forms
        with gr.Row():
            login_radio = gr.Radio(["Login", "Register"], label="Choose Action", value="Login")

        # Login form
        with gr.Column(visible=True) as login_column:
            username_login = gr.Textbox(label="Username", placeholder="Enter your username")
            password_login = gr.Textbox(label="Password", type="password", placeholder="Enter your password")
            new_api_key_login = gr.Textbox(label="New Gemini API Key (Optional)", placeholder="Enter new API key to update")
            login_button = gr.Button("Login")

        # Registration form
        with gr.Column(visible=False) as register_column:
            username_register = gr.Textbox(label="Username", placeholder="Choose a username")
            password_register = gr.Textbox(label="Password", type="password", placeholder="Choose a password")
            gemini_api_key_register = gr.Textbox(label="Gemini API Key", placeholder="Enter your Gemini API key")
            gr.Markdown("Password must be at least 8 characters long, contain uppercase and lowercase letters, a digit, and a special character.")
            register_button = gr.Button("Register")

        # Output components
        message_box = gr.Textbox(label="Message", interactive=False)
        token_output = gr.Textbox(visible=False)
        login_success = gr.Checkbox(visible=False)
        logged_in_username = gr.Textbox(visible=False)

    # Set up event handlers
    login_radio.change(
        lambda choice: (
            gr.update(visible=choice == "Login"),
            gr.update(visible=choice == "Register"),
        ),
        inputs=[login_radio],
        outputs=[login_column, register_column],
    )

    def validate_registration_input(username: str, password: str, api_key: str) -> Tuple[bool, str]:
        if not username or not password or not api_key:
            return False, "All fields are required."
        if not 6 <= len(username) <= 20:
            return False, "Username must be between 6 and 20 characters."
        if not re.match(r'^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&])[A-Za-z\d@$!%*?&]{8,}$', password):
            return False, "Password must be at least 8 characters long, contain uppercase and lowercase letters, a digit, and a special character."
        return True, ""

    def handle_registration(username: str, password: str, api_key: str) -> str:
        # Client-side validation
        is_valid, error_message = validate_registration_input(username, password, api_key)
        if not is_valid:
            return error_message

        # Server-side validation and registration
        result = register_api_call(username, password, api_key)
        if result.success:
            return "Registration successful. Please log in."
        else:
            return f"Registration failed: {result.error}"

    register_button.click(
        handle_registration,
        inputs=[username_register, password_register, gemini_api_key_register],
        outputs=[message_box]
    )

    def handle_login(username: str, password: str, new_api_key: str) -> Tuple[str, str, bool, str]:
        try:
            token, message, success, logged_in_username = login_api_call(username, password, new_api_key)
            if success:
                return token, f"Login successful. {message}", success, logged_in_username
            else:
                return "", message, False, ""
        except Exception as e:
            return "", str(e), False, ""

    login_button.click(
        handle_login,
        inputs=[username_login, password_login, new_api_key_login],
        outputs=[token_output, message_box, login_success, logged_in_username]
    )

    return {
        'username': username_login,
        'password': password_login,
        'new_api_key': new_api_key_login,
        'login_button': login_button,
        'message': message_box,
        'token': token_output,
        'login_success': login_success,
        'logged_in_username': logged_in_username,
        'login_function': handle_login
    }

def create_project_tab() -> Dict:
    """
    Create the components for the Project Management tab.
    
    Returns:
        Dict: A dictionary of Gradio components for the project tab
    """
    with gr.Column() as project_tab:
        project_action = gr.Radio(["Create New Project", "Choose Existing Project"], label="Action")
        new_project_name = gr.Textbox(label="New Project Name", visible=False)
        project_dropdown = gr.Dropdown(label="Select Existing Project", choices=[])
        proceed_button = gr.Button("Proceed")
        message = gr.Textbox(label="Message", interactive=False)
        selected_project = gr.Textbox(label="Selected Project", interactive=False)

    # Show/hide appropriate inputs based on selected action
    project_action.change(
        lambda x: (gr.update(visible=x=="Create New Project"), gr.update(visible=x=="Choose Existing Project")),
        inputs=[project_action],
        outputs=[new_project_name, project_dropdown]
    )

    return {
        "project_action": project_action,
        "new_project_name": new_project_name,
        "project_dropdown": project_dropdown,
        "proceed_button": proceed_button,
        "message": message,
        "selected_project": selected_project
    }

def create_llm_tab() -> Dict:
    """
    Create the components for the LLM tab.
    
    Returns:
        Dict: A dictionary of components for the LLM tab
    """
    with gr.Column() as LLM_Interface:
        project_name = gr.Markdown("## Current Project: None")
        
        with gr.Row():
            with gr.Column(scale=1):
                project_selector = gr.Dropdown(label="Select Project", choices=[])
                create_new_project_button = gr.Button("➕ Create New Project")
                file_upload = gr.File(label="Upload File")
                upload_button = gr.Button("Upload")
                upload_message = gr.Textbox(label="Upload Message", interactive=False)
                main_files_output = gr.Textbox(label="Main Files", interactive=False)
                temp_files_output = gr.Textbox(label="Temp Files", interactive=False)
                file_selector = gr.Dropdown(label="Select File", choices=[])
                
            with gr.Column(scale=2):
                chat_history = gr.Chatbot(label="Chat History")
                message_input = gr.Textbox(label="Message", placeholder="Type your message here...")
                send_button = gr.Button("Send")
                
            with gr.Column(scale=1):
                file_content = gr.Textbox(label="File Content", interactive=False)

    return {
        'project_name': project_name,
        'project_selector': project_selector,
        'create_new_project_button': create_new_project_button,
        'file_upload': file_upload,
        'upload_button': upload_button,
        'upload_message': upload_message,
        'main_files_output': main_files_output,
        'temp_files_output': temp_files_output,
        'file_selector': file_selector,
        'file_content': file_content,
        'chat_history': chat_history,
        'message_input': message_input,
        'send_button': send_button,
    }

def setup_llm_tab(components: Dict, token_state: gr.State, project_state: gr.State):
    """
    Set up the functionality for the LLM tab.
    
    Args:
        components (Dict): Dictionary of LLM tab components
        token_state (gr.State): State variable for user token
        project_state (gr.State): State variable for selected project
    
    Returns:
        Tuple[Callable, Callable]: Functions to update project list and file lists
    """
    def update_project_list():
        try:
            projects = list_projects(token_state.value)
            return gr.update(choices=[p["name"] for p in projects], value=project_state.value)
        except AuthenticationError:
            return gr.update(choices=[])
        except APIError as e:
            return gr.update(choices=[], value=None)

    def update_file_lists():
        project_name = project_state.value
        if not project_name:
            return "", ""

        try:
            files = list_files(token_state.value, project_name)
            main_files = "\n".join(files.get("main", []))
            temp_files = "\n".join(files.get("temp", []))
            return main_files, temp_files
        except AuthenticationError:
            return "", ""
        except APIError as e:
            return f"Error: {str(e)}", ""

    def change_project(project_name: str):
        project_state.value = project_name
        main_files, temp_files = update_file_lists()
        
        # Get the list of files
        try:
            files = list_files(token_state.value, project_name)
            file_choices = files.get("main", []) + files.get("temp", [])
        except (AuthenticationError, APIError):
            file_choices = []

        return (
            gr.update(value=f"## Current Project: {project_name}"),
            main_files,
            temp_files,
            "",  # Clear file content
            gr.update(choices=file_choices)
        )

    def upload_and_update(file):
        project_name = project_state.value
        if not project_name:
            return "No project selected", "", "", gr.update(choices=[])

        try:
            upload_result = upload_file(token_state.value, project_name, file)
            main_files, temp_files = update_file_lists()
            files = list_files(token_state.value, project_name)
            file_choices = files.get("main", []) + files.get("temp", [])
            return upload_result["message"], main_files, temp_files, gr.update(choices=file_choices)
        except AuthenticationError:
            return "Authentication failed. Please log in again.", "", "", gr.update(choices=[])
        except APIError as e:
            return f"Upload failed: {str(e)}", "", "", gr.update(choices=[])

    def send_message(message: str, history: List[Tuple[str, str]]) -> Tuple[List[Tuple[str, str]], str]:
        # This is a placeholder. Implement actual LLM integration here.
        history.append((message, "This is a placeholder response. The actual LLM integration is not implemented yet."))
        return history, ""

    def load_file_content(file_name: str):
        project_name = project_state.value
        if not project_name or not file_name:
            return ""
        
        try:
            # Implement a function to read file content
            content = read_file_content(token_state.value, project_name, file_name)
            return content
        except AuthenticationError:
            return "Authentication failed. Please log in again."
        except APIError as e:
            return f"Error loading file: {str(e)}"

    # Set up event handlers
    components['project_selector'].change(
        change_project,
        inputs=[components['project_selector']],
        outputs=[
            components['project_name'], 
            components['main_files_output'], 
            components['temp_files_output'], 
            components['file_content'],
            components['file_selector']
        ]
    )

    components['upload_button'].click(
        upload_and_update,
        inputs=[components['file_upload']],
        outputs=[
            components['upload_message'],
            components['main_files_output'], 
            components['temp_files_output'],
            components['file_selector']
        ]
    )

    components['send_button'].click(
        send_message,
        inputs=[components['message_input'], components['chat_history']],
        outputs=[components['chat_history'], components['message_input']]
    )

    components['file_selector'].change(
        load_file_content,
        inputs=[components['file_selector']],
        outputs=[components['file_content']]
    )

    return update_project_list, update_file_lists

# Note: You need to implement the read_file_content function
def read_file_content(token: str, project_name: str, file_name: str) -> str:
    """
    Read the content of a file from the server.
    This is a placeholder function. Implement the actual API call to read file content.
    """
    # Implement the actual API call here
    return f"Content of {file_name} in project {project_name}"
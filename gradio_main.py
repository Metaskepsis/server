import gradio as gr
from gradio_handlers import *
import logging
from typing import Dict, Tuple
from config import SERVER_HOST, SERVER_PORT

# Constants
LOGIN_TAB = "Login/Register"
PROJECT_TAB = "Project Management"
LLM_TAB = "LLM Interface"
CREATE_NEW_PROJECT = "Create New Project"
CHOOSE_EXISTING_PROJECT = "Choose Existing Project"

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_login_tab() -> Dict:
    with gr.Column():
        gr.Markdown("## Welcome to the Application")
        
        with gr.Row():
            login_radio = gr.Radio(["Login", "Register"], label="Choose Action", value="Login")

        with gr.Column(visible=True) as login_column:
            username_login = gr.Textbox(label="Username", placeholder="Enter your username")
            password_login = gr.Textbox(label="Password", type="password", placeholder="Enter your password")
            new_api_key_login = gr.Textbox(label="New Gemini API Key (Optional)", placeholder="Enter new API key to update")
            login_button = gr.Button("Login")

        with gr.Column(visible=False) as register_column:
            username_register = gr.Textbox(label="Username", placeholder="Choose a username")
            password_register = gr.Textbox(label="Password", type="password", placeholder="Choose a password")
            gemini_api_key_register = gr.Textbox(label="Gemini API Key", placeholder="Enter your Gemini API key")
            gr.Markdown("Password must be at least 8 characters long, contain uppercase and lowercase letters, a digit, and a special character.")
            register_button = gr.Button("Register")

        message_box = gr.Textbox(label="Message", interactive=False)

    login_radio.change(
        lambda choice: (
            gr.update(visible=choice == "Login"),
            gr.update(visible=choice == "Register"),
        ),
        inputs=[login_radio],
        outputs=[login_column, register_column],
    )

    return {
        'username': username_login,
        'password': password_login,
        'new_api_key': new_api_key_login,
        'login_button': login_button,
        'message': message_box,
        'register_button': register_button,
        'username_register': username_register,
        'password_register': password_register,
        'gemini_api_key_register': gemini_api_key_register
    }

def create_project_tab() -> Dict:
    with gr.Column() as project_tab:
        project_action = gr.Radio([CREATE_NEW_PROJECT, CHOOSE_EXISTING_PROJECT], label="Action")
        new_project_name = gr.Textbox(label="New Project Name", visible=False)
        project_dropdown = gr.Dropdown(label="Select Existing Project", choices=[])
        selected_project = gr.Textbox(label="Selected Project", interactive=False)
        proceed_button = gr.Button("Proceed")
        message = gr.Textbox(label="Message", interactive=False)

    project_action.change(
        lambda x: (gr.update(visible=x==CREATE_NEW_PROJECT), gr.update(visible=x==CHOOSE_EXISTING_PROJECT)),
        inputs=[project_action],
        outputs=[new_project_name, project_dropdown]
    )

    return {
        "project_action": project_action,
        "new_project_name": new_project_name,
        "project_dropdown": project_dropdown,
        "selected_project": selected_project,
        "proceed_button": proceed_button,
        "message": message
    }

def create_llm_tab() -> Dict:
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


def create_interface():
    with gr.Blocks() as interface:
        state = gr.State({"token": "", "username": "", "project": ""})

        with gr.Tabs() as tabs:
            with gr.Tab(LOGIN_TAB, id="login") as login_tab:
                login_components = create_login_tab()

            with gr.Tab(PROJECT_TAB, id="project", visible=False) as project_tab:
                project_components = create_project_tab()

            with gr.Tab(LLM_TAB, id="llm", visible=False) as llm_tab:
                llm_components = create_llm_tab()

        # Set up event handlers
        login_components['login_button'].click(
            handle_login,
            inputs=[login_components['username'], login_components['password'], login_components['new_api_key']],
            outputs=[state, login_tab, project_tab, llm_tab,
                     login_components['message'], project_components['project_dropdown'],
                     llm_components['project_name']]
        )

        login_components['register_button'].click(
            handle_registration,
            inputs=[login_components['username_register'], login_components['password_register'], login_components['gemini_api_key_register']],
            outputs=[login_components['message']]
        )

        project_components['project_action'].change(
            project_action_handler,
            inputs=[project_components['project_action'], project_components['new_project_name'], project_components['project_dropdown']],
            outputs=[project_components['message'], project_components['selected_project']]
        )

        project_components['proceed_button'].click(
            proceed_with_project,
            inputs=[state, project_components['selected_project']],
            outputs=[
                project_components['message'],
                project_tab,
                llm_tab,
                state,
                llm_components['project_name'],
                llm_components['main_files_output'],
                llm_components['temp_files_output'],
                llm_components['file_selector']
            ]
        )

        llm_components['project_selector'].change(
            update_project_selection,
            inputs=[llm_components['project_selector'], state],
            outputs=[
                llm_components['project_name'],
                state,
                llm_components['main_files_output'],
                llm_components['temp_files_output'],
                llm_components['file_selector']
            ]
        )

        llm_components['upload_button'].click(
            upload_and_update,
            inputs=[llm_components['file_upload'], state],
            outputs=[
                llm_components['upload_message'],
                llm_components['main_files_output'], 
                llm_components['temp_files_output'],
                llm_components['file_selector']
            ]
        )

        llm_components['send_button'].click(
            send_message,
            inputs=[llm_components['message_input'], llm_components['chat_history']],
            outputs=[llm_components['chat_history'], llm_components['message_input']]
        )

        llm_components['create_new_project_button'].click(
            switch_to_project_tab,
            outputs=[tabs, project_tab, llm_tab]
        )

        # Update project lists when tabs are selected or project state changes
        for trigger in [project_tab.select, llm_tab.select, state.change]:
            trigger(
                update_project_lists,
                inputs=[state],
                outputs=[project_components['project_dropdown'], llm_components['project_selector']]
            )

        async def update_llm_tab(state):
            token = state['token']
            project = state['project']
            projects = await update_project_lists(token)
            main_files, temp_files = await update_file_lists(token, project)
            return projects, main_files, temp_files

        llm_tab.select(
            update_llm_tab,
            inputs=[state],
            outputs=[
                llm_components['project_selector'],
                llm_components['main_files_output'],
                llm_components['temp_files_output']
            ]
        )

        # Add token validation when switching to project or LLM tabs
        for tab in [project_tab, llm_tab]:
            tab.select(
                check_and_update_token,
                inputs=[state],
                outputs=[state, login_tab, project_tab, llm_tab]
            )

    return interface

if __name__ == "__main__":
    demo = create_interface()
    demo.launch(server_name=SERVER_HOST, server_port=SERVER_PORT)
import gradio as gr
from gradio_handlers import *
from gradio_state_config import *
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_login_tab() -> Dict:
    with gr.Column():
        gr.Markdown("## Welcome to the Application")
        
        login_radio = gr.Radio(["Login", "Register"], label="Choose Action", value="Login")

        login_column = gr.Column(visible=True)
        with login_column:
            username_login = gr.Textbox(label="Username", placeholder="Enter your username")
            password_login = gr.Textbox(label="Password", type="password", placeholder="Enter your password")
            new_api_key_login = gr.Textbox(label="New Gemini API Key (Optional)", placeholder="Enter new API key to update")
            login_button = gr.Button("Login")

        register_column = gr.Column(visible=False)
        with register_column:
            username_register = gr.Textbox(label="Username", placeholder="Choose a username")
            password_register = gr.Textbox(label="Password", type="password", placeholder="Choose a password")
            gemini_api_key_register = gr.Textbox(label="Gemini API Key", placeholder="Enter your Gemini API key")
            gr.Markdown("Password must be at least 8 characters long, contain uppercase and lowercase letters, a digit, and a special character.")
            register_button = gr.Button("Register")

        message_box = gr.Textbox(label="Message", interactive=False)

    return {
        'username': username_login,
        'password': password_login,
        'new_api_key': new_api_key_login,
        'login_button': login_button,
        'message': message_box,
        'register_button': register_button,
        'username_register': username_register,
        'password_register': password_register,
        'gemini_api_key_register': gemini_api_key_register,
        'login_radio': login_radio,
        'login_column': login_column,
        'register_column': register_column
    }

def create_project_tab() -> Dict:
    with gr.Column() as project_tab:
        project_action = gr.Radio([CREATE_NEW_PROJECT, CHOOSE_EXISTING_PROJECT], label="Action", value=CREATE_NEW_PROJECT)
        new_project_name = gr.Textbox(label="New Project Name", visible=True)
        project_dropdown = gr.Dropdown(label="Select Existing Project", choices=[], visible=False)
        proceed_button = gr.Button("Proceed")
        message = gr.Textbox(label="Message", interactive=False)

    return {
        "project_action": project_action,
        "new_project_name": new_project_name,
        "project_dropdown": project_dropdown,
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
        state = gr.State(State().to_json())

        with gr.Tabs() as tabs:
            login_tab = gr.Tab(LOGIN_TAB, id=LOGIN_TAB)
            with login_tab:
                login_components = create_login_tab()

            project_tab = gr.Tab(PROJECT_TAB, id=PROJECT_TAB, visible=False)
            with project_tab:
                project_components = create_project_tab()

            llm_tab = gr.Tab(LLM_TAB, id=LLM_TAB, visible=False)
            with llm_tab:
                llm_components = create_llm_tab()

        def toggle_login_register(choice):
            try:
                return gr.update(visible=choice == "Login"), gr.update(visible=choice == "Register")
            except Exception as e:
                logger.error(f"Error in toggle_login_register: {str(e)}")
                return gr.update(visible=True), gr.update(visible=False)

        login_components['login_radio'].change(
            toggle_login_register,
            inputs=[login_components['login_radio']],
            outputs=[login_components['login_column'], login_components['register_column']]
        )

        async def login_handler(username, password, new_api_key, state_json):
            try:
                new_state, login_visible, project_visible, llm_visible, message, project_choices, project_name, main_files, temp_files, file_choices = await handle_login(username, password, new_api_key, state_json)
                return [
                    new_state,
                    gr.update(visible=login_visible),
                    gr.update(visible=project_visible),
                    gr.update(visible=llm_visible),
                    message,
                    gr.update(choices=project_choices),
                    gr.update(value=project_name),
                    main_files,
                    temp_files,
                    gr.update(choices=file_choices)
                ]
            except Exception as e:
                logger.error(f"Error in login_handler: {str(e)}")
                return [state_json, gr.update(visible=True), gr.update(visible=False), gr.update(visible=False), f"An error occurred: {str(e)}", gr.update(), gr.update(), "", "", gr.update()]

        login_components['login_button'].click(
            login_handler,
            inputs=[login_components['username'], login_components['password'], login_components['new_api_key'], state],
            outputs=[
                state,
                login_tab,
                project_tab,
                llm_tab,
                login_components['message'],
                project_components['project_dropdown'],
                llm_components['project_name'],
                llm_components['main_files_output'],
                llm_components['temp_files_output'],
                llm_components['file_selector']
            ]
        )

        login_components['register_button'].click(
            handle_registration,
            inputs=[login_components['username_register'], login_components['password_register'], login_components['gemini_api_key_register']],
            outputs=[login_components['message']]
        )

        def toggle_project_inputs(action):
            if action == CREATE_NEW_PROJECT:
                return gr.update(visible=True), gr.update(visible=False)
            else:
                return gr.update(visible=False), gr.update(visible=True)

        project_components['project_action'].change(
            toggle_project_inputs,
            inputs=[project_components['project_action']],
            outputs=[project_components['new_project_name'], project_components['project_dropdown']]
        )

        async def handle_create_project(new_name, state_json):
            message, new_state, project_names = await create_new_project(state_json, new_name)
            if "Error:" in message:
                return message, new_state, gr.update(), gr.update()
            return message, new_state, gr.update(choices=project_names), gr.update(choices=project_names)

        project_components['proceed_button'].click(
            handle_create_project,
            inputs=[
                project_components['new_project_name'],
                state
            ],
            outputs=[
                project_components['message'],
                state,
                project_components['project_dropdown'],
                llm_components['project_selector']
            ]
        )

        async def update_project_selection_wrapper(project_name, state):
            project_name, new_state, main_files, temp_files, file_choices = await update_project_selection(project_name, state)
            return [
                project_name,
                new_state,
                main_files,
                temp_files,
                gr.update(choices=file_choices)
            ]

        llm_components['project_selector'].change(
            update_project_selection_wrapper,
            inputs=[llm_components['project_selector'], state],
            outputs=[
                llm_components['project_name'],
                state,
                llm_components['main_files_output'],
                llm_components['temp_files_output'],
                llm_components['file_selector']
            ]
        )

        async def upload_and_update_wrapper(file, state):
            upload_message, main_files, temp_files, file_choices = await upload_and_update(file, state)
            return [
                upload_message,
                main_files,
                temp_files,
                gr.update(choices=file_choices)
            ]

        llm_components['upload_button'].click(
            upload_and_update_wrapper,
            inputs=[llm_components['file_upload'], state],
            outputs=[
                llm_components['upload_message'],
                llm_components['main_files_output'],
                llm_components['temp_files_output'],
                llm_components['file_selector']
            ]
        )

        async def send_message_wrapper(message, chat_history, state):
            chat_history, message = await send_message(message, chat_history, state)
            return [
                chat_history,
                message
            ]

        llm_components['send_button'].click(
            send_message_wrapper,
            inputs=[llm_components['message_input'], llm_components['chat_history'], state],
            outputs=[
                llm_components['chat_history'],
                llm_components['message_input']
            ]
        )

    return interface

if __name__ == "__main__":
    interface = create_interface()
    interface.launch()
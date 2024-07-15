import gradio as gr
from gradio_handlers import *
from gradio_state_config import State, SERVER_HOST, SERVER_PORT, LOGIN_TAB, PROJECT_TAB, LLM_TAB, CREATE_NEW_PROJECT, CHOOSE_EXISTING_PROJECT
import logging

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
        lambda choice: (choice == "Login", choice == "Register"),
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
        lambda x: (x==CREATE_NEW_PROJECT, x==CHOOSE_EXISTING_PROJECT),
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
        state = gr.State(State().to_json())

        with gr.Tabs() as tabs:
            with gr.TabItem(LOGIN_TAB, id=LOGIN_TAB) as login_tab:
                login_content = gr.Column(visible=True)
                with login_content:
                    login_components = create_login_tab()

            with gr.TabItem(PROJECT_TAB, id=PROJECT_TAB) as project_tab:
                project_content = gr.Column(visible=False)
                with project_content:
                    project_components = create_project_tab()

            with gr.TabItem(LLM_TAB, id=LLM_TAB) as llm_tab:
                llm_content = gr.Column(visible=False)
                with llm_content:
                    llm_components = create_llm_tab()

        def login_handler(username, password, new_api_key, state_json):
            new_state, login_visible, project_visible, llm_visible, message, project_choices, project_name, main_files, temp_files, file_choices = handle_login(username, password, new_api_key, state_json)
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

        login_components['login_button'].click(
            login_handler,
            inputs=[login_components['username'], login_components['password'], login_components['new_api_key'], state],
            outputs=[
                state,
                login_content,
                project_content,
                llm_content,
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

        def project_action_handler_wrapper(action, new_name, existing):
            message, selected = project_action_handler(action, new_name, existing)
            return [message, selected]

        project_components['project_action'].change(
            project_action_handler_wrapper,
            inputs=[project_components['project_action'], project_components['new_project_name'], project_components['project_dropdown']],
            outputs=[project_components['message'], project_components['selected_project']]
        )

        def proceed_with_project_wrapper(state, selected_project):
            message, project_visible, llm_visible, new_state, project_name, main_files, temp_files, file_choices = proceed_with_project(state, selected_project)
            return [
                message,
                gr.update(visible=project_visible),
                gr.update(visible=llm_visible),
                new_state,
                gr.update(value=project_name),
                main_files,
                temp_files,
                gr.update(choices=file_choices)
            ]

        project_components['proceed_button'].click(
            proceed_with_project_wrapper,
            inputs=[state, project_components['selected_project']],
            outputs=[
                project_components['message'],
                project_content,
                llm_content,
                state,
                llm_components['project_name'],
                llm_components['main_files_output'],
                llm_components['temp_files_output'],
                llm_components['file_selector']
            ]
        )

        def update_project_selection_wrapper(project_name, state):
            project_name, new_state, main_files, temp_files, file_choices = update_project_selection(project_name, state)
            return [
                gr.update(value=project_name),
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

        def upload_and_update_wrapper(file, state):
            message, main_files, temp_files, file_choices = upload_and_update(file, state)
            return [
                message,
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

        llm_components['send_button'].click(
            send_message,
            inputs=[llm_components['message_input'], llm_components['chat_history'], state],
            outputs=[llm_components['chat_history'], llm_components['message_input']]
        )

        def switch_to_project_tab_wrapper():
            tab, project_visible, llm_visible = switch_to_project_tab()
            return [gr.update(selected=tab), gr.update(visible=project_visible), gr.update(visible=llm_visible)]

        llm_components['create_new_project_button'].click(
            switch_to_project_tab_wrapper,
            outputs=[tabs, project_content, llm_content]
        )

        interface.load(
            lambda: (True, False, False),
            outputs=[login_tab, project_tab, llm_tab]
        )

        def update_project_lists_wrapper(state):
            project_choices, _ = update_project_lists(state)
            return [
                gr.update(choices=project_choices),
                gr.update(choices=project_choices)
            ]

        llm_tab.select(
            update_project_lists_wrapper,
            inputs=[state],
            outputs=[
                llm_components['project_selector'],
                project_components['project_dropdown']
            ]
        )

        def check_and_update_token_wrapper(state):
            new_state, login_visible, project_visible, llm_visible = check_and_update_token(state)
            return [new_state, gr.update(visible=login_visible), gr.update(visible=project_visible), gr.update(visible=llm_visible)]

        for tab in [project_tab, llm_tab]:
            tab.select(
                check_and_update_token_wrapper,
                inputs=[state],
                outputs=[state, login_content, project_content, llm_content]
            )

    return interface

if __name__ == "__main__":
    demo = create_interface()
    demo.launch(server_name=SERVER_HOST, server_port=SERVER_PORT)
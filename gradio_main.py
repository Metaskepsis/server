import gradio as gr
from gradio_handlers import *
from gradio_state_config import *
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def toggle_login_register(choice):
    try:
        return gr.update(visible=choice == "Login"), gr.update(visible=choice == "Register")
    except Exception as e:
        logger.error(f"Error in toggle_login_register: {str(e)}")
        return gr.update(visible=True), gr.update(visible=False)

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
                main_files_output = temp_files_output = gr.Dataframe(headers=["Main Files"],row_count=(5, "dynamic"),col_count=(1, "fixed"),interactive=False,wrap=True)
                temp_files_output = temp_files_output = gr.Dataframe(headers=["Temp Files"],row_count=(5, "dynamic"),col_count=(1, "fixed"),interactive=False,wrap=True)
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

        login_components['login_radio'].change(
            toggle_login_register,
            inputs=[login_components['login_radio']],
            outputs=[login_components['login_column'], login_components['register_column']]
        )

        login_components['login_button'].click(
            handle_login,
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

        project_components['project_action'].change(
            lambda action: (gr.update(visible=action == CREATE_NEW_PROJECT), gr.update(visible=action != CREATE_NEW_PROJECT)),
            inputs=[project_components['project_action']],
            outputs=[project_components['new_project_name'], project_components['project_dropdown']]
        )

        project_components['proceed_button'].click(
            handle_project_selection,
            inputs=[
                project_components['project_action'],
                project_components['new_project_name'],
                project_components['project_dropdown'],
                state
            ],
            outputs=[
                project_components['message'],
                state,
                project_components['project_dropdown'],
                llm_components['project_selector'],
                gr.Checkbox(visible=False)  # This is a temporary checkbox to hold the boolean value
            ]
        ).then(
            conditional_tab_switch,
            inputs=[gr.Checkbox(visible=False)],  # This corresponds to the temporary checkbox
            outputs=[login_tab, project_tab, llm_tab]
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
            inputs=[llm_components['message_input'], llm_components['chat_history'], state],
            outputs=[
                llm_components['chat_history'],
                llm_components['message_input']
            ]
        )
        llm_components['create_new_project_button'].click(
            switch_to_project_tab,
            outputs=[
                login_tab, 
                project_tab, 
                llm_tab, 
                project_components['project_action'],
                project_components['new_project_name'],
                project_components['project_dropdown']
            ]
        )
        tabs.select(
            update_project_dropdown,
            inputs=[state],
            outputs=[project_components['project_dropdown']],
            js="(index) => index === 1"  # Assuming project tab is index 1
        )

    return interface

if __name__ == "__main__":
    interface = create_interface()
    interface.launch()
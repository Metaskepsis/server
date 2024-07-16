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
        
        with gr.Column(visible=True) as new_project_column:
            new_project_name = gr.Textbox(label="New Project Name", placeholder="Enter project name")
            gr.Markdown("A new project needs a description, this can be either using a pilot file or by answering some questions.")
            with gr.Row():
                upload_file_button = gr.Button("Upload a file")
                create_empty_project_button = gr.Button("Create empty project")
                create_project_by_inquiry_button = gr.Button("Answer some questions")
            file_upload = gr.File(label="Upload File", visible=False)

            
            chat_interface = gr.Column(visible=False)
            with chat_interface:
                chat_history = gr.Chatbot(label="Chat History")
                message_input = gr.Textbox(label="Message", placeholder="Type your message here...")
                send_button = gr.Button("Send")

        with gr.Column(visible=False) as existing_project_column:
            project_dropdown = gr.Dropdown(label="Select Existing Project", choices=[])
            proceed_button = gr.Button("Proceed", visible=True)

        message = gr.Textbox(label="Message", interactive=False)

    return {
        "project_action": project_action,
        "new_project_name": new_project_name,
        "upload_file_button": upload_file_button,
        "create_empty_project_button": create_empty_project_button,
        "create_project_by_inquiry_button": create_project_by_inquiry_button,
        "file_upload": file_upload,
        "project_dropdown": project_dropdown, 
        "proceed_button": proceed_button,
        "message": message,
        "new_project_column": new_project_column,
        "existing_project_column": existing_project_column,
        "chat_interface": chat_interface,
        "chat_history": chat_history,
        "message_input": message_input,
        "send_button": send_button
    }


def create_llm_tab() -> Dict:
    with gr.Column() as LLM_Interface:
        project_name = gr.Markdown("## Current Project: None")
        
        # Create a container for the horizontally scrollable content
        with gr.Row() as row:
            with gr.Column(scale=1, min_width=300):
                file_selector = gr.Dropdown(label="Select File", choices=[])
                file_upload = gr.File(label="Upload File")
                upload_button = gr.Button("Upload")
                message = gr.Textbox(label=" Message", interactive=False)
                project_selector = gr.Dropdown(label="Select Project", choices=[], allow_custom_value=True, interactive=True)
                create_new_project_button = gr.Button("➕ Create New Project")
            with gr.Column(scale=1, min_width=300):
                chat_history = gr.Chatbot(label="Chat History")
                reply_to_metaskepsis = gr.Textbox(label="Your input", placeholder="Reply to metaskepsis here")
                send_button = gr.Button("Send")
                
            with gr.Column(scale=1, min_width=300):
                file_content1 = gr.HTML(label="File Content")
                visualize_button1 = gr.Button("Visualize Selected File")
                file_content2 = gr.HTML(label="File Content")
                visualize_button2 = gr.Button("Visualize Selected File")
    return {
        'project_name': project_name,
        'project_selector': project_selector,
        'create_new_project_button': create_new_project_button,
        'file_upload': file_upload,
        'upload_button': upload_button,
        'message': message,
        'file_selector': file_selector,
        'file_content1': file_content1,
        'file_content2': file_content2,
        'visualize_button1': visualize_button1,
        'visualize_button2': visualize_button2,
        'chat_history': chat_history,
        'reply_to_metaskepsis': reply_to_metaskepsis,
        'send_button': send_button}
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
                llm_components['file_selector'],
                llm_components['project_selector']  # Add this line
            ]
        )

        login_components['register_button'].click(
            handle_registration,
            inputs=[login_components['username_register'], login_components['password_register'], login_components['gemini_api_key_register']],
            outputs=[login_components['message']]
        )

        project_components['project_action'].change(
            fn=lambda choice: (
                gr.update(visible=choice==CREATE_NEW_PROJECT),
                gr.update(visible=choice==CHOOSE_EXISTING_PROJECT)
            ),
            inputs=[project_components['project_action']],
            outputs=[
                project_components['new_project_column'],
                project_components['existing_project_column']
            ]
        )
        project_components['upload_file_button'].click(
            handle_upload_file_button,
            inputs=[state],
            outputs=[project_components['file_upload'], project_components['message']]
        )

        project_components['create_empty_project_button'].click(
            handle_create_empty_project,
            inputs=[project_components['new_project_name'], state],
            outputs=[project_components['message'], state, project_components['project_dropdown'], llm_components['project_selector']]
        )

        project_components['create_project_by_inquiry_button'].click(
            handle_answer_questions,
            inputs=[project_components['new_project_name'], state],
            outputs=[project_components['message'], state, project_components['chat_interface'], project_components['chat_history']]
        )

        project_components['send_button'].click(
            send_message_project_tab,
            inputs=[project_components['message_input'], project_components['chat_history'], state],
            outputs=[project_components['chat_history'], project_components['message_input'], state]
        )


        project_components['project_dropdown'].change(
        handle_project_selection,
        inputs=[project_components['project_dropdown'], state],
        outputs=[
            project_components['message'],
            state,
            project_components['project_dropdown']
        ]
    )

        project_components['proceed_button'].click(
            handle_proceed_button,
            inputs=[state],
            outputs=[
                login_tab, 
                project_tab, 
                llm_tab,
                project_components['message']
            ]
        )


        llm_components['project_selector'].change(
            update_project_selection,
            inputs=[llm_components['project_selector'], state],
            outputs=[
                llm_components['project_name'],
                state,
                llm_components['file_selector'],
                llm_components['message'],
                llm_components['project_selector']
            ]
        )

        llm_components['file_selector'].change(
        handle_file_selection,
        inputs=[llm_components['file_selector'], state],
        outputs=[state, llm_components['message']]
    )

        llm_components['upload_button'].click(
            upload_and_update,
            inputs=[llm_components['file_upload'], state],
            outputs=[
                llm_components['message'],
                llm_components['file_upload'],  # Add this line
                llm_components['file_selector']
            ]
        )

        llm_components['send_button'].click(
            send_message,
            inputs=[llm_components['reply_to_metaskepsis'], llm_components['chat_history'], state],
            outputs=[
                llm_components['chat_history'],
                llm_components['reply_to_metaskepsis'],
            ]
        )

        llm_components['create_new_project_button'].click(
            switch_to_project_tab,
            outputs=[login_tab,project_tab,llm_tab])
        
        llm_components['visualize_button1'].click(
    visualize_file,
    inputs=[llm_components['file_selector'], state],
    outputs=[llm_components['file_content1']])

        llm_components['visualize_button2'].click(
    visualize_file, 
    inputs=[llm_components['file_selector'], state],
    outputs=[llm_components['file_content2']])

    return interface

if __name__ == "__main__":
    interface = create_interface()
    interface.launch()
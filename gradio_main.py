import gradio as gr
from login_tab import create_login_tab
from project_tab import create_project_tab, create_project, choose_project, list_projects
from llm_tab import create_llm_tab

def create_interface():
    """
    Create and return the main Gradio interface for the application.
    This function sets up the entire user interface, including login, project management, and LLM interaction.
    """
    with gr.Blocks() as interface:
        # State variables to keep track of user token and selected project across tabs
        token_state = gr.State()
        project_state = gr.State()

        # Main tab structure of the application
        with gr.Tabs() as tabs:
            # Login/Register tab
            with gr.Tab("Login/Register", id="login") as login_tab:
                login_components = create_login_tab()

            # Project Management tab (initially hidden)
            with gr.Tab("Project Management", id="project", visible=False) as project_tab:
                project_components = create_project_tab()

            # LLM Interface tab (initially hidden)
            with gr.Tab("LLM Interface", id="llm", visible=False) as llm_tab:
                llm_components = create_llm_tab()

        def handle_login(token, message, success):
            """
            Handle the login process and update the UI accordingly.
            
            Args:
            token (str): The authentication token received upon successful login.
            message (str): The message to display to the user.
            success (bool): Indicates whether the login was successful.

            Returns:
            tuple: Contains updates for various UI components based on login success.
            """
            if success:
                # Successful login: Show project tab and hide login tab
                return (
                    token,  # Update token_state
                    gr.update(visible=False),  # Hide login tab
                    gr.update(visible=True),  # Show project tab
                    message,  # Display login message
                    gr.update(selected="Project Management"),  # Switch to project management tab
                )
            else:
                # Failed login: Keep login tab visible
                return (
                    "",  # Clear token_state
                    gr.update(visible=True),  # Keep login tab visible
                    gr.update(visible=False),  # Keep project tab hidden
                    message,  # Display error message
                    gr.update(),  # No change in tab selection
                )

        # Connect login button click to handle_login function
        login_components['login_button'].click(
            handle_login,
            inputs=[login_components['token'], login_components['message'], login_components['login_success']],
            outputs=[token_state, login_tab, project_tab, login_components['message'], tabs]
        )

        def handle_project_action(token, action, project_name):
            """
            Handle project creation or selection and update the UI accordingly.
            
            Args:
            token (str): The user's authentication token.
            action (str): The action to perform ('Create New Project' or 'Choose Existing Project').
            project_name (str): The name of the project to create or select.

            Returns:
            tuple: Contains updates for various UI components based on the project action.
            """
            if action == "Create New Project":
                message, project, dropdown = create_project(token, project_name)
            else:
                message, project = choose_project(token, project_name)
                dropdown = gr.update(choices=list_projects(token))
            
            return (
                message,  # Display action result message
                project,  # Update project_state
                dropdown,  # Update project dropdown
                gr.update(visible=project is not None),  # Show LLM tab if project is selected
                gr.update(selected="LLM Interface") if project is not None else gr.update(),  # Switch to LLM tab if project is selected
            )

        # Connect project creation button to handle_project_action function
        project_components['create_button'].click(
            handle_project_action,
            inputs=[token_state, gr.State("Create New Project"), project_components['new_project_name']],
            outputs=[project_components['message'], project_state, project_components['project_dropdown'], llm_tab, tabs]
        )

        # Connect project selection button to handle_project_action function
        project_components['choose_button'].click(
            handle_project_action,
            inputs=[token_state, gr.State("Choose Existing Project"), project_components['project_dropdown']],
            outputs=[project_components['message'], project_state, project_components['project_dropdown'], llm_tab, tabs]
        )

        # Update project list when the project tab becomes visible
        project_tab.select(
            lambda token: gr.update(choices=list_projects(token)),
            inputs=[token_state],
            outputs=[project_components['project_dropdown']]
        )

        # Update project dropdown when switching to "Choose Existing Project"
        project_action = project_components['project_dropdown'].parent.parent.children[0].children[0]
        project_action.change(
            project_components['toggle_and_update'],
            inputs=[project_action, token_state],
            outputs=[
                project_components['new_project_name'].parent,
                project_components['project_dropdown'].parent,
                project_components['project_dropdown']
            ]
        )

        # Connect LLM interface buttons to their respective functions
        llm_components['list_button'].click(
            llm_components['list_function'],
            inputs=[token_state, project_state],
            outputs=[llm_components['files_output']]
        )

        llm_components['upload_button'].click(
            llm_components['upload_function'],
            inputs=[token_state, project_state, llm_components['file_upload']],
            outputs=[llm_components['upload_output']]
        )

        llm_components['send_button'].click(
            llm_components['send_function'],
            inputs=[token_state, llm_components['message']],
            outputs=[llm_components['response']]
        )

    return interface

if __name__ == "__main__":
    demo = create_interface()
    demo.launch()
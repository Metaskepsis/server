# gradio_main.py

import gradio as gr
from typing import Tuple
from tabs import create_login_tab, create_project_tab, create_llm_tab, setup_llm_tab
from gradio_util import (
    list_projects,
    handle_login_result,
    create_project,
    list_files,
    validate_token,
    AuthenticationError
)
import requests
import logging
logging.basicConfig(level=logging.INFO)

# After successful login


def create_interface():
    """
    Create and return the main Gradio interface for the application.
    This function sets up the entire user interface, including login, project management, and LLM interaction.
    
    Returns:
        gr.Blocks: The main Gradio interface
    """
    with gr.Blocks() as interface:
        # State variables to keep track of user token and selected project across tabs
        token_state = gr.State("")  # Stores the user's authentication token
        username_state = gr.State("")  # Stores the logged-in username
        project_state = gr.State("")  # Stores the currently selected project

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

        # Connect login button click to handle_login function and then process the result
        # Connect login button click to handle_login function and then process the result
        login_components['login_button'].click(
            login_components['login_function'],
            inputs=[login_components['username'], login_components['password'], login_components['new_api_key']],
            outputs=[login_components['token'], login_components['message'], 
                    login_components['login_success'], login_components['logged_in_username']]
        ).then(
            handle_login_result,
            inputs=[login_components['token'], login_components['message'], 
                    login_components['login_success'], login_components['logged_in_username']],
            outputs=[token_state, username_state, login_tab, project_tab, llm_tab, 
                    login_components['message'], project_components['project_dropdown'], 
                    project_state, llm_components['project_name']]
        ).then(
            lambda token, project: list_files(token, project) if project else {"main": [], "temp": []},
            inputs=[token_state, project_state],
            outputs=[gr.State()]  # Store file list result in a temporary state
        ).then(
            lambda files, project: (
                gr.update(value=f"## Current Project: {project}" + (" (No files)" if not any(files.values()) else "")),
                "\n".join(files.get("main", [])),
                "\n".join(files.get("temp", [])),
                gr.update(choices=files.get("main", []) + files.get("temp", []))
            ),
            inputs=[gr.State(), project_state],  # Use the temporary state from previous step
            outputs=[
                llm_components['project_name'],
                llm_components['main_files_output'],
                llm_components['temp_files_output'],
                llm_components['file_selector']
            ]
        )
        # Function to handle project creation or selection
        def project_action_handler(token, action, new_project_name, existing_project):
            if action == "Create New Project":
                result = create_project(token, new_project_name)
                if isinstance(result, dict) and "message" in result:
                    message = result["message"]
                    project = new_project_name
                else:
                    message = "Failed to create project"
                    project = None
            else:
                message = "Project selected"
                project = existing_project

            projects = list_projects(token)
            project_names = [p["name"] for p in projects]
            
            files = list_files(token, project)
            main_files = "\n".join(files.get("main", []))
            temp_files = "\n".join(files.get("temp", []))
            
            return (
                message, project, 
                gr.update(choices=project_names, value=project),  # Update Project tab's dropdown
                gr.update(choices=project_names, value=project),  # Update LLM tab's project selector
                *update_visibility(False, False, True),
                project,
                gr.update(value=f"## Current Project: {project}"),
                main_files, temp_files
            )

        # Connect project action button to project_action_handler function
        project_components['proceed_button'].click(
            project_action_handler,
            inputs=[token_state, project_components['project_action'], 
                    project_components['new_project_name'], project_components['project_dropdown']],
            outputs=[project_components['message'], project_components['selected_project'], 
                     project_components['project_dropdown'], llm_components['project_selector'], 
                     project_tab, project_tab, llm_tab, 
                     project_state, llm_components['project_name'], 
                     llm_components['main_files_output'], llm_components['temp_files_output']]
        )

        # Function to update project selection in LLM tab
        def update_project_selection(project_name, token):
            if project_name:
                projects = list_projects(token)
                project = next((p for p in projects if p["name"] == project_name), None)
                if project:
                    files = list_files(token, project_name)
                    main_files = "\n".join(files.get("main", []))
                    temp_files = "\n".join(files.get("temp", []))
                    return (
                        gr.update(value=f"## Current Project: {project_name}"),
                        project_name,
                        main_files,
                        temp_files
                    )
            return (
                gr.update(value="## Current Project: None"),
                "",
                "", ""
            )

        # Add event handler for the project selector in the LLM tab
        llm_components['project_selector'].change(
            update_project_selection,
            inputs=[llm_components['project_selector'], token_state],
            outputs=[
                llm_components['project_name'],
                project_state,
                llm_components['main_files_output'],
                llm_components['temp_files_output']
            ]
        )

        # Function to update project lists in both Project and LLM tabs
        def update_project_lists(token):
            try:
                projects = list_projects(token)
                project_names = [p["name"] for p in projects]
                return (
                    gr.update(choices=project_names),  # Project tab dropdown
                    gr.update(choices=project_names),  # LLM tab project selector
                )
            except AuthenticationError:
                # If authentication fails, don't change tab visibility
                return (
                    gr.update(choices=[]),     # Project tab dropdown
                    gr.update(choices=[]),     # LLM tab project selector
                )


        # Update project lists when tabs are selected or project state changes
        for trigger in [project_tab.select, llm_tab.select, project_state.change]:
            trigger(
                update_project_lists,
                inputs=[token_state],
                outputs=[
                    project_components['project_dropdown'], 
                    llm_components['project_selector']
                ]
            )

        # Set up the LLM tab functionality
        update_project_list_func, update_file_lists_func = setup_llm_tab(llm_components, token_state, project_state)

        # Function to update LLM tab
        def update_llm_tab():
            projects = update_project_list_func()
            file_lists = update_file_lists_func()
            if isinstance(file_lists, tuple) and len(file_lists) == 2:
                main_files, temp_files = file_lists
            else:
                main_files = temp_files = ""
                logging.warning(f"Unexpected return from update_file_lists_func: {file_lists}")
            return projects, main_files, temp_files

        # Update LLM tab when it becomes visible
        llm_tab.select(
            update_llm_tab,
            outputs=[
                llm_components['project_selector'],
                llm_components['main_files_output'],
                llm_components['temp_files_output']
            ]
        )

        # Function to switch to the project tab
        def switch_to_project_tab():
            return gr.update(selected="project"), gr.update(visible=True), gr.update(visible=False)

        # Handle "Create New Project" button click in LLM tab
        llm_components['create_new_project_button'].click(
            switch_to_project_tab,
            outputs=[tabs, project_tab, llm_tab]
        ).then(
            lambda token: list_projects(token),
            inputs=[token_state],
            outputs=[project_components['project_dropdown']]
        )

        # Function to check and update token validity
        def check_and_update_token(token):
            if validate_token(token):
                return token, gr.update(visible=False), gr.update(visible=True), gr.update(visible=True)
            else:
                return "", gr.update(visible=True), gr.update(visible=False), gr.update(visible=False)

        # Add token validation when switching to project or LLM tabs
        for tab in [project_tab, llm_tab]:
            tab.select(
                check_and_update_token,
                inputs=[token_state],
                outputs=[token_state, login_tab, project_tab, llm_tab]
            )

    return interface

def update_visibility(login_visible: bool, project_visible: bool, llm_visible: bool) -> Tuple[gr.update, gr.update, gr.update]:
    """
    Update the visibility of main interface tabs.
    
    Args:
        login_visible (bool): Whether the login tab should be visible
        project_visible (bool): Whether the project tab should be visible
        llm_visible (bool): Whether the LLM tab should be visible
    
    Returns:
        Tuple[gr.update, gr.update, gr.update]: Update instructions for each tab's visibility
    """
    return tuple(gr.update(visible=v) for v in (login_visible, project_visible, llm_visible))

if __name__ == "__main__":
    demo = create_interface()
    demo.launch(server_name="127.0.0.1", server_port=7860)
import gradio as gr
import requests

# API endpoint for backend communication
API_URL = "http://localhost:8000"

def create_project(token: str, project_name: str) -> tuple:
    """
    Create a new project via API call.

    Args:
        token (str): User authentication token.
        project_name (str): Name of the project to create.

    Returns:
        tuple: (message, project_name, dropdown_update)
            message (str): Status message of the operation.
            project_name (str or None): Name of the created project, or None if failed.
            dropdown_update (gr.update): Gradio update object for the project dropdown.
    """
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.post(f"{API_URL}/create_project", json={"project_name": project_name}, headers=headers)
    if response.status_code == 200:
        projects = list_projects(token)
        return response.json()["message"], project_name, gr.update(choices=projects)
    else:
        return f"Failed to create project: {response.json().get('detail', 'Unknown error')}", None, gr.update()

def list_projects(token: str) -> list:
    """
    Fetch the list of projects for the authenticated user.

    Args:
        token (str): User authentication token.

    Returns:
        list: List of project names, or empty list if failed.
    """
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(f"{API_URL}/list_projects", headers=headers)
    if response.status_code == 200:
        return response.json()
    else:
        return []

def choose_project(token: str, project_name: str) -> tuple:
    """
    Verify and select an existing project.

    Args:
        token (str): User authentication token.
        project_name (str): Name of the project to select.

    Returns:
        tuple: (message, project_name)
            message (str): Status message of the operation.
            project_name (str or None): Name of the selected project, or None if failed.
    """
    if project_name:
        headers = {"Authorization": f"Bearer {token}"}
        response = requests.get(f"{API_URL}/verify_project/{project_name}", headers=headers)
        if response.status_code == 200:
            return f"Project '{project_name}' selected", project_name
        else:
            return "Failed to verify project", None
    else:
        return "No project selected", None

def create_project_tab() -> dict:
    """
    Create and return the project management tab components.

    Returns:
        dict: A dictionary containing all the Gradio components for the project management tab.
    """
    with gr.Column():
        gr.Markdown("## Project Management")
        
        with gr.Row():
            project_action = gr.Radio(
                ["Create New Project", "Choose Existing Project"],
                label="Choose Action",
                value="Create New Project"
            )

        with gr.Column(visible=True) as create_column:
            new_project_name = gr.Textbox(label="New Project Name", placeholder="Enter project name")
            create_project_button = gr.Button("Create Project")

        with gr.Column(visible=False) as choose_column:
            project_dropdown = gr.Dropdown(
                label="Select Existing Project",
                interactive=True,
                allow_custom_value=False,  # Prevents typing in the dropdown
                choices=[]  # Initialize with empty list
            )
            choose_project_button = gr.Button("Choose Project")

        output_message = gr.Textbox(label="Output", interactive=False)
        selected_project = gr.State(None)

    def toggle_visibility_and_update_dropdown(choice: str, token: str) -> tuple:
        """
        Toggle visibility of create and choose project columns based on user selection
        and update the project dropdown if "Choose Existing Project" is selected.

        Args:
            choice (str): The selected action ("Create New Project" or "Choose Existing Project").
            token (str): User authentication token.

        Returns:
            tuple: (create_column_update, choose_column_update, dropdown_update)
                create_column_update (gr.update): Update object for create project column visibility.
                choose_column_update (gr.update): Update object for choose project column visibility.
                dropdown_update (gr.update): Update object for project dropdown choices.
        """
        create_visible = choice == "Create New Project"
        choose_visible = choice == "Choose Existing Project"
        
        dropdown_update = gr.update()
        if choose_visible:
            projects = list_projects(token)
            dropdown_update = gr.update(choices=projects)
        
        return (
            gr.update(visible=create_visible),
            gr.update(visible=choose_visible),
            dropdown_update
        )

    project_action.change(
        toggle_visibility_and_update_dropdown,
        inputs=[project_action, gr.State("")],  # We'll pass the token from gradio_main.py
        outputs=[create_column, choose_column, project_dropdown],
    )

    return {
        'new_project_name': new_project_name,
        'create_button': create_project_button,
        'project_dropdown': project_dropdown,
        'choose_button': choose_project_button,
        'message': output_message,
        'selected_project': selected_project,
        'create_function': create_project,
        'choose_function': choose_project,
        'list_function': list_projects,
        'toggle_and_update': toggle_visibility_and_update_dropdown
    }
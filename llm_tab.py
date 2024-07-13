import gradio as gr
import requests

API_URL = "http://localhost:8000"

def list_files(token, project_name):
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(f"{API_URL}/list_files/{project_name}", headers=headers)
    if response.status_code == 200:
        return "\n".join(response.json())
    else:
        return f"Failed to list files: {response.json().get('detail', 'Unknown error')}"

def upload_file(token, project_name, file):
    headers = {"Authorization": f"Bearer {token}"}
    if file is None:
        return "No file selected"
    
    file_name = file.name
    file_content = file.read()
    file_type = getattr(file, 'type', 'application/octet-stream')
    
    files = {'file': (file_name, file_content, file_type)}
    
    response = requests.post(f"{API_URL}/upload/{project_name}", files=files, headers=headers)
    if response.status_code == 200:
        return response.json()["message"]
    else:
        return f"Failed to upload file: {response.json().get('detail', 'Unknown error')}"

def contact_supervisor(token, message):
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.post(f"{API_URL}/contact_supervisor", json={"message": message}, headers=headers)
    if response.status_code == 200:
        return response.json()["response"]
    else:
        return f"Failed to send message: {response.json().get('detail', 'Unknown error')}"

def create_llm_tab():
    with gr.Row():
        with gr.Column():
            project_name_input = gr.Textbox(label="Project Name")
            list_files_button = gr.Button("List Files")
            files_output = gr.Textbox(label="Files", interactive=False)
            
            file_upload = gr.File(label="Upload File")
            upload_button = gr.Button("Upload")
            upload_output = gr.Textbox(label="Upload Output", interactive=False)

        with gr.Column():
            supervisor_message = gr.Textbox(label="Message to Supervisor/LLM")
            contact_supervisor_button = gr.Button("Send Message")
            supervisor_response = gr.Textbox(label="Supervisor/LLM Response", interactive=False)

    return {
        'project_name': project_name_input,
        'list_button': list_files_button,
        'files_output': files_output,
        'list_function': list_files,
        'file_upload': file_upload,
        'upload_button': upload_button,
        'upload_output': upload_output,
        'upload_function': upload_file,
        'message': supervisor_message,
        'send_button': contact_supervisor_button,
        'response': supervisor_response,
        'send_function': contact_supervisor
    }

def setup_llm_tab(tab, token):
    tab['list_button'].click(
        tab['list_function'],
        inputs=[lambda: token, tab['project_name']],
        outputs=[tab['files_output']]
    )
    
    tab['upload_button'].click(
        tab['upload_function'],
        inputs=[lambda: token, tab['project_name'], tab['file_upload']],
        outputs=[tab['upload_output']]
    )
    
    tab['send_button'].click(
        tab['send_function'],
        inputs=[lambda: token, tab['message']],
        outputs=[tab['response']]
    )

# This part would be in your main Gradio application file
def create_gradio_app(token):
    with gr.Blocks() as demo:
        llm_tab = create_llm_tab()
        setup_llm_tab(llm_tab, token)
    return demo

# Example usage
if __name__ == "__main__":
    # You would get this token from your login process
    example_token = "your_auth_token_here"
    app = create_gradio_app(example_token)
    app.launch()
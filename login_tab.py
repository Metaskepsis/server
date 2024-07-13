import gradio as gr
import requests
import re

# API endpoint for authentication and registration
API_URL = "http://localhost:8000"

def login(username, password):
    """
    Attempt to log in the user.
    
    Args:
    username (str): The user's username
    password (str): The user's password
    
    Returns:
    tuple: (access_token, message, success_flag)
    """
    response = requests.post(f"{API_URL}/token", data={"username": username, "password": password})
    if response.status_code == 200:
        data = response.json()
        return data["access_token"], data.get("message", "Login successful"), True
    else:
        error_detail = response.json().get("detail", "An unknown error occurred")
        return "", f"Login failed: {error_detail}", False

def validate_password(password):
    """
    Validate the password against security criteria.
    
    Args:
    password (str): The password to validate
    
    Returns:
    str or None: Error message if validation fails, None if password is valid
    """
    if not password:
        return "Password cannot be empty."
    if len(password) < 8:
        return "Password must be at least 8 characters long."
    if not re.search(r"[A-Z]", password):
        return "Password must contain at least one uppercase letter."
    if not re.search(r"[a-z]", password):
        return "Password must contain at least one lowercase letter."
    if not re.search(r"\d", password):
        return "Password must contain at least one digit."
    if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", password):
        return "Password must contain at least one special character."
    return None

def register_with_api_key(username, email, password, gemini_api_key):
    """
    Attempt to register a new user with a Gemini API key.
    
    Args:
    username (str): The new user's username
    email (str): The new user's email
    password (str): The new user's password
    gemini_api_key (str): The new user's Gemini API key
    
    Returns:
    str: A message indicating the result of the registration attempt
    """
    password_error = validate_password(password)
    if password_error:
        return password_error
    
    try:
        response = requests.post(f"{API_URL}/register", json={
            "username": username,
            "email": email,
            "password": password,
            "gemini_api_key": gemini_api_key
        })
        
        if response.status_code == 200:
            return "Registration successful. Please log in."
        else:
            # Try to get JSON error message, fall back to text or status code
            try:
                error_message = response.json().get('error', 'An unknown error occurred')
            except requests.exceptions.JSONDecodeError:
                error_message = response.text if response.text else f"HTTP Error: {response.status_code}"
            
            return f"Registration failed: {error_message}"
    except requests.RequestException as e:
        return f"Registration failed due to a network error: {str(e)}"

def create_login_tab():
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
            login_button = gr.Button("Login")

        # Registration form
        with gr.Column(visible=False) as register_column:
            username_register = gr.Textbox(label="Username", placeholder="Choose a username")
            email_register = gr.Textbox(label="Email", placeholder="Enter your email")
            password_register = gr.Textbox(label="Password", type="password", placeholder="Choose a password")
            gemini_api_key_register = gr.Textbox(label="Gemini API Key", placeholder="Enter your Gemini API key")
            gr.Markdown("Password must be at least 8 characters long, contain uppercase and lowercase letters, a digit, and a special character.")
            register_button = gr.Button("Register")

        # Output components
        message_box = gr.Textbox(label="Message", interactive=False)
        token_output = gr.Textbox(visible=False)
        login_success = gr.Checkbox(visible=False)

    def toggle_visibility(choice):
        """
        Toggle visibility of login and register forms based on radio button selection.
        """
        return (
            gr.update(visible=choice == "Login"),
            gr.update(visible=choice == "Register"),
        )

    # Set up event handlers
    login_radio.change(
        toggle_visibility,
        inputs=[login_radio],
        outputs=[login_column, register_column],
    )

    login_button.click(
        login,
        inputs=[username_login, password_login],
        outputs=[token_output, message_box, login_success]
    )

    register_button.click(
        register_with_api_key,
        inputs=[username_register, email_register, password_register, gemini_api_key_register],
        outputs=[message_box]
    )

    # Return a dictionary of all components
    return {
        'username': username_login,
        'password': password_login,
        'login_button': login_button,
        'message': message_box,
        'token': token_output,
        'login_success': login_success,
        'login_function': login
    }
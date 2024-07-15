from fastapi import FastAPI, Depends, HTTPException, status, File, UploadFile, Request, Body
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from typing import List, Dict
import re
import os
import shutil
import json
from pydantic import BaseModel
from datetime import timedelta, datetime
from fastapi_auth import *
import logging
import google.generativeai as genai

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
# Initialize FastAPI app
app = FastAPI(
    title="Project Management API",
    description="API for user management, project creation, and file uploads",
    version="1.0.0"
)

class ProjectCreate(BaseModel):
    project_name: str


# OAuth2 scheme for token authentication
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

@app.middleware("http")
async def log_requests(request: Request, call_next):
    logger.info(f"Received {request.method} request to {request.url}")
    response = await call_next(request)
    logger.info(f"Returned {response.status_code} for {request.method} {request.url}")
    return response

@app.post("/token", response_model=Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    # Check if the username exists
    user = get_user(form_data.username)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Username does not exist",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Verify password
    if not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Handle Gemini API key
    new_api_key = form_data.scopes[0] if form_data.scopes else ""  # Assuming the new key is passed in the scopes field
    
    if not new_api_key:
        # Check if the existing API key is valid
        if not validate_gemini_api_key(user.gemini_api_key):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Saved Gemini API key is no longer valid",
            )
    else:
        # Validate and update the new API key
        if validate_gemini_api_key(new_api_key):
            update_user_api_key(user.username, new_api_key)
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Provided Gemini API key is not valid",
            )
    
    # Create access token
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}


@app.post("/register", status_code=status.HTTP_201_CREATED)
async def register_new_user(user: UserCreate):
    # Step 1: Validate username format
    if not validate_username(user.username):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid username format"
        )
    
    # Step 2: Check if username already exists
    if user_exists(user.username):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username already exists"
        )
    
    # Step 3: Validate password format
    if not validate_password(user.password):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid password format"
        )
    
    # Step 4: Validate Gemini API key
    if not await validate_gemini_api_key(user.gemini_api_key):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid Gemini API key"
        )
    
    # Step 5: Create user directory and save user data
    try:
        user_dir = os.path.join(USERS_DIRECTORY, user.username)
        os.makedirs(os.path.join(user_dir, "projects"), exist_ok=True)
        
        hashed_password = get_password_hash(user.password)
        user_dict = {
            "username": user.username,
            "hashed_password": hashed_password,
            "disabled": False,
            "gemini_api_key": user.gemini_api_key,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "last_login": None
        }
        
        with open(os.path.join(user_dir, "credentials.json"), "w") as f:
            json.dump(user_dict, f)
        
        return {"message": "User registered successfully"}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error during registration: {str(e)}"
        )

@app.post("/projects")
async def create_project(project: ProjectCreate, current_user: User = Depends(get_current_active_user)):
    """
    Create a new project for the current user with 'main' and 'temp' folders.
    """
    project_name = project.project_name

    # Validate project name
    if not re.match(r'^[a-zA-Z0-9_-]+$', project_name):
        raise HTTPException(status_code=400, detail="Invalid project name. Use only letters, numbers, underscores, and hyphens.")
    
    project_dir = os.path.join(USERS_DIRECTORY, current_user.username, "projects", project_name)
    if os.path.exists(project_dir):
        raise HTTPException(status_code=400, detail="Project already exists")
    
    try:
        # Create main project directory
        os.makedirs(project_dir)
        
        # Create 'main' and 'temp' subdirectories
        os.makedirs(os.path.join(project_dir, "main"))
        os.makedirs(os.path.join(project_dir, "temp"))
        
        # Create project info file with timestamp
        project_info = {
            "name": project_name,
            "created_at": datetime.now().isoformat()
        }
        with open(os.path.join(project_dir, "project_info.json"), "w") as f:
            json.dump(project_info, f)
        
        return {"message": f"Project '{project_name}' created successfully with 'main' and 'temp' folders", "created_at": project_info["created_at"]}
    except Exception as e:
        # If an error occurs, remove the partially created project directory
        shutil.rmtree(project_dir, ignore_errors=True)
        raise HTTPException(status_code=500, detail=f"Failed to create project: {str(e)}")

@app.get("/users/me/", response_model=User)
async def read_users_me(current_user: User = Depends(get_current_active_user)):
    """
    Get information about the current user.
    """
    return current_user

@app.get("/users/me/api_key")
async def get_user_api_key(current_user: UserInDB = Depends(get_current_active_user)):
    """
    Get the current user's Gemini API key.
    """
    return {"api_key": current_user.gemini_api_key}

@app.post("/users/me/update_api_key")
async def update_user_api_key(new_api_key: str, current_user: UserInDB = Depends(get_current_active_user)):
    """
    Update the current user's Gemini API key.
    """
    if new_api_key.strip():  # If a new key is provided
        if not validate_gemini_api_key(new_api_key):
            raise HTTPException(status_code=400, detail="new_api_key is not valid")
        try:
            update_user_api_key(current_user.username, new_api_key)
            return {"message": "API key updated successfully"}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to update API key: {str(e)}")
    else:  # If no new key is provided, check the existing key
        if not validate_gemini_api_key(current_user.gemini_api_key):
            return {"message": "Your current Gemini API key is invalid or expired"}
        return {"message": "Current API key is valid"}
    
@app.post("/projects")
async def create_project(project_name: str, current_user: User = Depends(get_current_active_user)):
    """
    Create a new project for the current user with 'main' and 'temp' folders.
    """
    # Validate project name
    if not re.match(r'^[a-zA-Z0-9_-]+$', project_name):
        raise HTTPException(status_code=400, detail="Invalid project name. Use only letters, numbers, underscores, and hyphens.")
    
    project_dir = os.path.join(USERS_DIRECTORY, current_user.username, "projects", project_name)
    if os.path.exists(project_dir):
        raise HTTPException(status_code=400, detail="Project already exists")
    
    try:
        # Create main project directory
        os.makedirs(project_dir)
        
        # Create 'main' and 'temp' subdirectories
        os.makedirs(os.path.join(project_dir, "main"))
        os.makedirs(os.path.join(project_dir, "temp"))
        
        # Create project info file with timestamp
        project_info = {
            "name": project_name,
            "created_at": datetime.now().isoformat()
        }
        with open(os.path.join(project_dir, "project_info.json"), "w") as f:
            json.dump(project_info, f)
        
        return {"message": f"Project '{project_name}' created successfully with 'main' and 'temp' folders", "created_at": project_info["created_at"]}
    except Exception as e:
        # If an error occurs, remove the partially created project directory
        shutil.rmtree(project_dir, ignore_errors=True)
        raise HTTPException(status_code=500, detail=f"Failed to create project: {str(e)}")

@app.get("/projects", response_model=List[Dict[str, str]])
async def list_projects(current_user: User = Depends(get_current_active_user)):
    """
    List all projects for the current user with their timestamps.
    """
    projects_dir = os.path.join(USERS_DIRECTORY, current_user.username, "projects")
    projects = []
    for project_name in os.listdir(projects_dir):
        project_dir = os.path.join(projects_dir, project_name)
        if os.path.isdir(project_dir):
            info_file = os.path.join(project_dir, "project_info.json")
            if os.path.exists(info_file):
                with open(info_file, "r") as f:
                    info = json.load(f)
                projects.append({"name": project_name, "created_at": info["created_at"]})
            else:
                projects.append({"name": project_name, "created_at": ""})
    
    return sorted(projects, key=lambda x: x["created_at"], reverse=True)

@app.get("/projects/{project_name}/files")
async def list_files(project_name: str, current_user: User = Depends(get_current_active_user)):
    logger.info(f"Received request to list files for project '{project_name}' from user '{current_user.username}'")
    project_dir = os.path.join(USERS_DIRECTORY, current_user.username, "projects", project_name)
    if not os.path.exists(project_dir):
        logger.warning(f"Project directory not found for '{project_name}' (user: {current_user.username})")
        raise HTTPException(status_code=404, detail="Project not found")
    
    main_dir = os.path.join(project_dir, "main")
    temp_dir = os.path.join(project_dir, "temp")
    
    main_files = [f for f in os.listdir(main_dir)] if os.path.exists(main_dir) else []
    temp_files = [f for f in os.listdir(temp_dir)] if os.path.exists(temp_dir) else []
    
    logger.info(f"Files found for project '{project_name}' (user: {current_user.username}) - Main: {main_files}, Temp: {temp_files}")
    return {"main": main_files, "temp": temp_files}

@app.post("/upload/{project_name}")
async def upload_file(
    project_name: str, 
    file: UploadFile = File(...), 
    current_user: User = Depends(get_current_active_user)
):
    """
    Upload a file to a specific project's temp folder for the current user.
    """
    project_dir = os.path.join(USERS_DIRECTORY, current_user.username, "projects", project_name)
    if not os.path.exists(project_dir):
        raise HTTPException(status_code=404, detail="Project not found")
    
    temp_dir = os.path.join(project_dir, "temp")
    os.makedirs(temp_dir, exist_ok=True)
    
    file_location = os.path.join(temp_dir, file.filename)
    try:
        with open(file_location, "wb+") as file_object:
            shutil.copyfileobj(file.file, file_object)
        return {"message": f"File '{file.filename}' uploaded to project '{project_name}' temp folder"}
    except IOError:
        raise HTTPException(status_code=500, detail="Error uploading file")

@app.get("/validate_token")
async def validate_token(current_user: User = Depends(get_current_active_user)):
    """
    Validate the user's token.
    """
    return {"valid": True}

@app.get("/projects/{project_name}/files/{file_name}")
async def get_file_content(
    project_name: str,
    file_name: str,
    current_user: User = Depends(get_current_active_user)
):
    """
    Get the content of a specific file in a project.
    """
    project_dir = os.path.join(USERS_DIRECTORY, current_user.username, "projects", project_name)
    if not os.path.exists(project_dir):
        raise HTTPException(status_code=404, detail="Project not found")
    
    main_file = os.path.join(project_dir, "main", file_name)
    temp_file = os.path.join(project_dir, "temp", file_name)
    
    if os.path.exists(main_file):
        file_path = main_file
    elif os.path.exists(temp_file):
        file_path = temp_file
    else:
        raise HTTPException(status_code=404, detail="File not found")
    
    try:
        with open(file_path, "r") as file:
            content = file.read()
        return {"content": content}
    except IOError:
        raise HTTPException(status_code=500, detail="Error reading file")

@app.delete("/projects/{project_name}/files/{file_name}")
async def delete_file(
    project_name: str,
    file_name: str,
    current_user: User = Depends(get_current_active_user)
):
    """
    Delete a specific file from a project.
    """
    project_dir = os.path.join(USERS_DIRECTORY, current_user.username, "projects", project_name)
    if not os.path.exists(project_dir):
        raise HTTPException(status_code=404, detail="Project not found")
    
    main_file = os.path.join(project_dir, "main", file_name)
    temp_file = os.path.join(project_dir, "temp", file_name)
    
    if os.path.exists(main_file):
        os.remove(main_file)
        return {"message": f"File '{file_name}' deleted from main folder"}
    elif os.path.exists(temp_file):
        os.remove(temp_file)
        return {"message": f"File '{file_name}' deleted from temp folder"}
    else:
        raise HTTPException(status_code=404, detail="File not found")

@app.post("/projects/{project_name}/llm")
async def send_message_to_llm(
    project_name: str,
    message: str = Body(..., embed=True),
    current_user: UserInDB = Depends(get_current_active_user)
):
    """
    Send a message to the LLM and get a response.
    """
    try:
        genai.configure(api_key=current_user.gemini_api_key)
        model = genai.GenerativeModel('gemini-pro')
        response = model.generate_content(message)
        return {"response": response.text}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error communicating with LLM: {str(e)}")

@app.post("/projects/{project_name}/files/{file_name}/move")
async def move_file(
    project_name: str,
    file_name: str,
    current_user: User = Depends(get_current_active_user)
):
    """
    Move a file from the temp folder to the main folder.
    """
    project_dir = os.path.join(USERS_DIRECTORY, current_user.username, "projects", project_name)
    if not os.path.exists(project_dir):
        raise HTTPException(status_code=404, detail="Project not found")
    
    temp_file = os.path.join(project_dir, "temp", file_name)
    main_file = os.path.join(project_dir, "main", file_name)
    
    if not os.path.exists(temp_file):
        raise HTTPException(status_code=404, detail="File not found in temp folder")
    
    try:
        shutil.move(temp_file, main_file)
        return {"message": f"File '{file_name}' moved from temp to main folder"}
    except IOError:
        raise HTTPException(status_code=500, detail="Error moving file")



if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
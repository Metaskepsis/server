from fastapi import FastAPI, Depends, HTTPException, status, File, UploadFile
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from typing import List, Dict
import os
import shutil
import json
from pydantic import BaseModel
from datetime import timedelta, datetime
from auth import (
    User, UserCreate, Token, UserInDB, user_exists, validate_username, validate_password,
    validate_gemini_api_key, register_user, get_user,  verify_password,create_access_token, get_current_active_user, USERS_DIRECTORY,
    ACCESS_TOKEN_EXPIRE_MINUTES
)

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

@app.post("/projects/{project_name}/folders")
async def create_project_folder(project_name: str, folder_name: str, current_user: User = Depends(get_current_active_user)):
    """
    Create a new folder in a specific project.
    """
    project_dir = os.path.join(USERS_DIRECTORY, current_user.username, "projects", project_name)
    if not os.path.exists(project_dir):
        raise HTTPException(status_code=404, detail="Project not found")
    
    folder_path = os.path.join(project_dir, folder_name)
    if os.path.exists(folder_path):
        return {"message": f"Folder '{folder_name}' already exists in project '{project_name}'"}
    
    try:
        os.makedirs(folder_path)
        return {"message": f"Folder '{folder_name}' created successfully in project '{project_name}'"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creating folder: {str(e)}")


@app.post("/register", status_code=status.HTTP_201_CREATED)
async def register_new_user(user: UserCreate):
    if not validate_username(user.username):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid username format")
    
    if not validate_password(user.password):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid password format")
    
    if user_exists(user.username):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Username already exists")
    
    if not validate_gemini_api_key(user.gemini_api_key):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid Gemini API key")
    
    try:
        new_user = register_user(user)
        return {"message": "User registered successfully"}
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error during registration: {str(e)}")
    
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
    Create a new project for the current user with a timestamp.
    """
    project_dir = os.path.join(USERS_DIRECTORY, current_user.username, "projects", project_name)
    if os.path.exists(project_dir):
        raise HTTPException(status_code=400, detail="Project already exists")
    
    os.makedirs(project_dir)
    
    # Create project info file with timestamp
    project_info = {
        "name": project_name,
        "created_at": datetime.now().isoformat()
    }
    with open(os.path.join(project_dir, "project_info.json"), "w") as f:
        json.dump(project_info, f)
    
    return {"message": f"Project '{project_name}' created successfully", "created_at": project_info["created_at"]}

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
    """
    List files in a specific project for the current user.
    """
    project_dir = os.path.join(USERS_DIRECTORY, current_user.username, "projects", project_name)
    if not os.path.exists(project_dir):
        raise HTTPException(status_code=404, detail="Project not found")
    
    main_dir = os.path.join(project_dir, "main")
    temp_dir = os.path.join(project_dir, "temp")
    
    main_files = [f for f in os.listdir(main_dir)] if os.path.exists(main_dir) else []
    temp_files = [f for f in os.listdir(temp_dir)] if os.path.exists(temp_dir) else []
    
    return {"main": main_files, "temp": temp_files}

@app.post("/upload/{project_name}")
async def upload_file(
    project_name: str, 
    file: UploadFile = File(...), 
    current_user: User = Depends(get_current_active_user)
):
    """
    Upload a file to a specific project for the current user.
    """
    project_dir = os.path.join(USERS_DIRECTORY, current_user.username, "projects", project_name)
    if not os.path.exists(project_dir):
        raise HTTPException(status_code=404, detail="Project not found")
    file_location = os.path.join(project_dir, file.filename)
    try:
        with open(file_location, "wb+") as file_object:
            shutil.copyfileobj(file.file, file_object)
        return {"message": f"File '{file.filename}' uploaded to project '{project_name}'"}
    except IOError:
        raise HTTPException(status_code=500, detail="Error uploading file")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
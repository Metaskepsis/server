from fastapi import Depends, FastAPI, File, UploadFile, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from datetime import timedelta
import os
import shutil
from typing import List
from pydantic import BaseModel
from fastapi_auth import *

app = FastAPI(
    title="Project Management API",
    version="1.0",
    description="API for project management and file uploads",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

PROJECTS_DIRECTORY = "./projects"

if not os.path.exists(PROJECTS_DIRECTORY):
    os.makedirs(PROJECTS_DIRECTORY)

class ProjectCreate(BaseModel):
    project_name: str

class SupervisorMessage(BaseModel):
    message: str

@app.post("/token", response_model=Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    user = authenticate_user(form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

@app.post("/register")
async def register_user_endpoint(user: UserCreate):
    return register_user(user)

@app.post("/create_project")
async def create_project(project: ProjectCreate, current_user: User = Depends(get_current_active_user)):
    project_dir = os.path.join(PROJECTS_DIRECTORY, current_user.username, project.project_name)
    if os.path.exists(project_dir):
        raise HTTPException(status_code=400, detail="Project already exists")
    os.makedirs(os.path.join(project_dir, "main"))
    os.makedirs(os.path.join(project_dir, "temp"))
    return {"message": f"Project '{project.project_name}' created successfully"}

@app.get("/list_projects", response_model=List[str])
async def list_projects(current_user: User = Depends(get_current_active_user)):
    user_projects_dir = os.path.join(PROJECTS_DIRECTORY, current_user.username)
    if not os.path.exists(user_projects_dir):
        return []
    return [d for d in os.listdir(user_projects_dir) if os.path.isdir(os.path.join(user_projects_dir, d))]

@app.get("/list_files/{project_name}", response_model=List[str])
async def list_files(project_name: str, current_user: User = Depends(get_current_active_user)):
    project_dir = os.path.join(PROJECTS_DIRECTORY, current_user.username, project_name)
    if not os.path.exists(project_dir):
        raise HTTPException(status_code=404, detail="Project not found")
    main_files = [f"main/{f}" for f in os.listdir(os.path.join(project_dir, "main"))]
    temp_files = [f"temp/{f}" for f in os.listdir(os.path.join(project_dir, "temp"))]
    return main_files + temp_files

@app.post("/upload/{project_name}")
async def upload_file(project_name: str, file: UploadFile = File(...), current_user: User = Depends(get_current_active_user)):
    project_dir = os.path.join(PROJECTS_DIRECTORY, current_user.username, project_name)
    if not os.path.exists(project_dir):
        raise HTTPException(status_code=404, detail="Project not found")
    file_location = os.path.join(project_dir, "main", file.filename)
    with open(file_location, "wb") as f:
        shutil.copyfileobj(file.file, f)
    return {"message": f"File '{file.filename}' uploaded successfully to project '{project_name}'"}

@app.post("/contact_supervisor")
async def contact_supervisor(message: SupervisorMessage, current_user: User = Depends(get_current_active_user)):
    # Placeholder function to contact supervisor
    return {"message": f"Message sent to supervisor: {message.message}"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

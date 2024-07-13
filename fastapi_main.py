from fastapi import Depends, FastAPI, File, UploadFile, HTTPException, status
from fastapi.responses import JSONResponse
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from datetime import timedelta
import os
import shutil
from typing import List, Union, Any
from pydantic import BaseModel, Field
from dotenv import load_dotenv
from langchain.agents import AgentExecutor
from langchain.agents.format_scratchpad.tools import format_to_tool_messages
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.prompts import ChatPromptTemplate, HumanMessagePromptTemplate, SystemMessagePromptTemplate
from auth import (
    User, UserCreate, Token, ACCESS_TOKEN_EXPIRE_MINUTES,
    get_current_active_user, authenticate_user, create_access_token,
    register_user, USERS_DIRECTORY
)

load_dotenv()

app = FastAPI(
    title="Project Management API",
    version="1.0",
    description="API for project management, file uploads, and AI supervisor",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if not os.path.exists(USERS_DIRECTORY):
    os.makedirs(USERS_DIRECTORY)

# Supervisor setup
llm = ChatGoogleGenerativeAI(model="gemini-1.5-flash")
tools = []

def get_folder_structure(username: str):
    user_dir = os.path.join(USERS_DIRECTORY, username)
    structure = {}
    
    for root, dirs, files in os.walk(user_dir):
        current = structure
        path = os.path.relpath(root, user_dir).split(os.sep)
        for folder in path:
            if folder not in current:
                current[folder] = {}
            current = current[folder]
        for file in files:
            current[file] = None
    
    return structure

# Minimal "hello world" supervisor prompt template
supervisor_prompt_template = ChatPromptTemplate.from_messages([
    SystemMessagePromptTemplate.from_template(
        "You are a helpful AI assistant. Respond to the user's input."
    ),
    HumanMessagePromptTemplate.from_template("{input}")
])

agent = (
    {
        "input": lambda x: x["input"],
        "agent_scratchpad": lambda x: format_to_tool_messages(x["intermediate_steps"]),
        "chat_history": lambda x: x["chat_history"],
        "folder_structure": lambda x: get_folder_structure(x["username"]),
    }
    | supervisor_prompt_template
    | llm.bind_tools(tools)
)

class ProjectCreate(BaseModel):
    project_name: str

class SupervisorMessage(BaseModel):
    message: str

class SupervisorInput(BaseModel):
    input: str
    chat_history: List[Union[HumanMessage, AIMessage, ToolMessage]] = Field(
        ...,
        extra={"widget": {"type": "chat", "input": "input", "output": "output"}},
    )
    username: str

class SupervisorOutput(BaseModel):
    output: Any

agent_executor = (
    AgentExecutor(agent=agent, tools=tools, verbose=True)
    .with_types(input_type=SupervisorInput, output_type=SupervisorOutput)
    .with_config({"run_name": "agent"})
)

@app.post("/token")
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
    return JSONResponse(content={"access_token": access_token, "token_type": "bearer", "message": "Login successful"})

def validate_gemini_api_key(api_key: str) -> bool:
    try:
        llm = ChatGoogleGenerativeAI(model="gemini-1.5-flash", google_api_key=api_key)
        response = llm.invoke("Hello, are you working?")
        return True
    except Exception as e:
        print(f"Error validating Gemini API key: {str(e)}")
        return False

@app.post("/register")
async def register_user_endpoint(user: UserCreate):
    try:
        # First, validate the Gemini API key
        if not validate_gemini_api_key(user.gemini_api_key):
            return JSONResponse(
                content={"error": "Invalid Gemini API key"},
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        # If the API key is valid, proceed with user registration
        result = register_user(user)
        return JSONResponse(content=result, status_code=200)
    except HTTPException as e:
        return JSONResponse(content={"error": str(e.detail)}, status_code=e.status_code)
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)

@app.post("/create_project")
async def create_project(project: ProjectCreate, current_user: User = Depends(get_current_active_user)):
    project_dir = os.path.join(USERS_DIRECTORY, current_user.username, "projects", project.project_name)
    if os.path.exists(project_dir):
        raise HTTPException(status_code=400, detail="Project already exists")
    os.makedirs(os.path.join(project_dir, "main"))
    os.makedirs(os.path.join(project_dir, "temp"))
    return {"message": f"Project '{project.project_name}' created successfully"}

@app.get("/verify_project/{project_name}")
async def verify_project(project_name: str, current_user: User = Depends(get_current_active_user)):
    project_dir = os.path.join(USERS_DIRECTORY, current_user.username, "projects", project_name)
    if os.path.exists(project_dir):
        return {"message": "Project verified"}
    else:
        raise HTTPException(status_code=404, detail="Project not found")

@app.get("/list_projects", response_model=List[str])
async def list_projects(current_user: User = Depends(get_current_active_user)):
    user_projects_dir = os.path.join(USERS_DIRECTORY, current_user.username, "projects")
    if not os.path.exists(user_projects_dir):
        return []
    return [d for d in os.listdir(user_projects_dir) if os.path.isdir(os.path.join(user_projects_dir, d))]

@app.get("/list_files/{project_name}", response_model=List[str])
async def list_files(project_name: str, current_user: User = Depends(get_current_active_user)):
    project_dir = os.path.join(USERS_DIRECTORY, current_user.username, "projects", project_name)
    if not os.path.exists(project_dir):
        raise HTTPException(status_code=404, detail="Project not found")
    main_files = [f"main/{f}" for f in os.listdir(os.path.join(project_dir, "main"))]
    temp_files = [f"temp/{f}" for f in os.listdir(os.path.join(project_dir, "temp"))]
    return main_files + temp_files

@app.post("/upload/{project_name}")
async def upload_file(project_name: str, file: UploadFile = File(...), current_user: User = Depends(get_current_active_user)):
    project_dir = os.path.join(USERS_DIRECTORY, current_user.username, "projects", project_name)
    if not os.path.exists(project_dir):
        raise HTTPException(status_code=404, detail="Project not found")
    file_location = os.path.join(project_dir, "main", file.filename)
    with open(file_location, "wb") as f:
        shutil.copyfileobj(file.file, f)
    return {"message": f"File '{file.filename}' uploaded successfully to project '{project_name}'"}

@app.post("/contact_supervisor")
async def contact_supervisor(message: SupervisorMessage, current_user: User = Depends(get_current_active_user)):
    supervisor_input = SupervisorInput(input=message.message, chat_history=[], username=current_user.username)
    result = await agent_executor.ainvoke(supervisor_input)
    return {"response": result.output}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
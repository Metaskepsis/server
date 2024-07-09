from fastapi import FastAPI
from langserve import add_routes
from Supervisor import agent_executor

app = FastAPI(
    title="LangChain Server",
    version="1.0",
    description="Spin up a simple api server using LangChain's Runnable interfaces",
)


add_routes(app, agent_executor)

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="localhost", port=8000)

from dotenv import load_dotenv
from typing import Any, List, Union
from langchain.agents import AgentExecutor
from langchain.agents.format_scratchpad.tools import format_to_tool_messages
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from prompts.Supervisor_prompt import supervisor_prompt_template
from langserve.pydantic_v1 import BaseModel, Field
from tools.Local_tools import get_folder_structure

load_dotenv()

llm = ChatGoogleGenerativeAI(model="gemini-1.0-pro")

tools = []

# def prompt_trimmer(messages: List[Union[HumanMessage, AIMessage, ToolMessage]]):
#     return messages[-10:]

agent = (
    {
        "input": lambda x: x["input"],
        "agent_scratchpad": lambda x: format_to_tool_messages(x["intermediate_steps"]),
        "chat_history": lambda x: x["chat_history"],
        "folder_structure": lambda x: get_folder_structure(),
    }
    | supervisor_prompt_template
    # | prompt_trimmer
    | llm.bind_tools(tools)
)


class Input(BaseModel):
    input: str
    chat_history: List[Union[HumanMessage, AIMessage, ToolMessage]] = Field(
        ...,
        extra={"widget": {"type": "chat", "input": "input", "output": "output"}},
    )


class Output(BaseModel):
    output: Any


agent_executor = (
    AgentExecutor(agent=agent, tools=tools, verbose=True)
    .with_types(input_type=Input, output_type=Output)
    .with_config({"run_name": "agent"})
)

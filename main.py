from typing_extensions import TypedDict
from typing import Annotated
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.chat_models import init_chat_model
from langgraph.graph import StateGraph,START,END
from langchain_core.tools import tool
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode,tools_condition
from dotenv import load_dotenv
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import interrupt,Command
import requests
import os

memory=MemorySaver()

load_dotenv()

class Projectstate(TypedDict):
    messages:Annotated[list,add_messages]
    file_path:str
    executive_summary:str
    dev_summary:str
    tech_stack:str
    linkedin_post:str

NOTION_API_KEY = os.getenv("NOTION_API_KEY")
DATABASE_ID = "2328a5f387db80aa85dde9c7d3cd7b6e"

url = "https://api.notion.com/v1/pages"

@tool
def push_to_notion(linkedin_post:str) -> str:
    '''Push the given linkedin_post information to the notion page.'''
    decision=interrupt(f"Push the following content to notion:\n{linkedin_post}")
    if decision.lower()=="yes":

        headers = {
            "Authorization": f"Bearer {NOTION_API_KEY}",
            "Content-Type": "application/json",
            "Notion-Version": "2022-06-28"
        }

        data = {
            "parent": {"database_id": DATABASE_ID},
            "properties": {
                "Title": {
                    "title": [{"text": {"content": "Ai_generated_Post"}}]
                },
                "Post Content": {
                    "rich_text": [{"text": {"content": linkedin_post}}]
                }
            }
        }

        response = requests.post(url, headers=headers, json=data)
        if response.status_code == 200 or response.status_code == 201:
            return "Successfully added to Notion"
        else:
            return f"Failed: {response.status_code} - {response.text}"
    else:
        return "Failed to post the message"
    
tools=[push_to_notion]

llm=init_chat_model("google_genai:gemini-2.0-flash")
llm_with_tools=llm.bind_tools(tools)

def summarize_code(state:Projectstate)->Projectstate:
    file_path=state["messages"][-1].content
    with open(file_path,"r") as f:
        txt=f.read()
    text_splitter=RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100)
    chunks=text_splitter.split_text(txt)
    prev_summary=llm.invoke(f"""Provide a summary for the following code:{chunks[0]}
                            Give a short description of the imports used in a tabular format.
            Explain each function used in the file.
            Try to keep the summary under 4000 words.""")
    for chunk in chunks[1:]:
        prev_summary=llm.invoke(
            "Here is the current summary:\n"
            f"{prev_summary}\n\n"
            "Please refine this summary by integrating the summary for the following code:\n"
            f"{chunk}\n"
            """Give a short description of the imports used in a tabular format.
            Explain each function used in the file.
            Try to keep the summary under 4000 words.
            Avoid providing duplicate data and do not provide any extra code or extra details"""
        )
    state["dev_summary"]=llm.invoke(f"Check if the following summary is correctly formatted and make the necessary changes if required.Avoid adding any additional ai based messages \nSummary:{prev_summary}")
    state["executive_summary"]=llm.invoke(f"Using the following summary generate another summary for non technical executives.Avoid adding any additional ai based messages Summary:{state['dev_summary']}")
    state["tech_stack"]=llm.invoke(f"Using the summary provide a list of the techstack used.Avoid adding any additional ai based messages Summary: {state['dev_summary']}")
    state["messages"].append(state["dev_summary"])
    print("Summarized")
    return state

def linkedin_post_gen(state:Projectstate)->Projectstate:
    state["linkedin_post"]=llm.invoke(f"""
Using the provided summary generate an engaging description for a linkedin post.
Generate a description in 10-15 lines in a professional tone.
Add hooks such as " How it works:","What sets this project apart?","Tech stack used"
Use the provided tools to gather the latest news and the research papers if necessary.
Summary:{state['messages']}""")
    state['messages'].append(f'''Push the linkedin post to notion.
                             pass the following information:
                             {state["linkedin_post"]}''')
    return state

def poster(state:Projectstate)->Projectstate:
    state['messages'].append(llm_with_tools.invoke(state["messages"]))
    return state

builder=StateGraph(Projectstate)

builder.add_node("summarizer",summarize_code)
builder.add_node("post_generator",linkedin_post_gen)
builder.add_node("poster",poster)
builder.add_node("tools",ToolNode(tools))

builder.add_edge(START,"summarizer")
builder.add_edge("summarizer","post_generator")
builder.add_edge("post_generator","poster")
builder.add_conditional_edges("poster",tools_condition)
builder.add_edge("tools",END)

graph=builder.compile(checkpointer=memory)

# config={'configurable': {'thread_id':'1'}}

# state=graph.invoke({'messages':"partition.py"},config=config)
# print(state.get("__interrupt__"))

# decision=input("Should i post the content(yes/no):")
# state=graph.invoke(Command(resume=decision),config=config)
# print(state["messages"][-1].content)
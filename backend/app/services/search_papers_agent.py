import os
import requests
from bs4 import BeautifulSoup
from typing import TypedDict, List
from langgraph.graph import StateGraph
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from langchain_groq import ChatGroq
from dotenv import load_dotenv
import json

load_dotenv()
model = ChatGroq(model_name="llama-3.3-70b-versatile", temperature=0.7)

class AgentState(TypedDict):
    topic: str
    scraped_data: str
    cleaned_data: List[dict]

def srape_scholar_papers_node(state: AgentState):
    topic = state["topic"]
    url = f"https://scholar.google.com/scholar?q={topic}"
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
        )
    }
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code != 200:
            scraped = f"Error: Received status code {response.status_code}"
        else:
            soup = BeautifulSoup(response.text, "html.parser")
            results = []
            for idx, div in enumerate(soup.find_all("div", class_="gs_ri")):
                if idx >= 5:  
                    break
                title_elem = div.find("h3", class_="gs_rt")
                if title_elem:
                    link_tag = title_elem.find("a")
                    title = title_elem.get_text(strip=True)
                    link = link_tag["href"] if link_tag and link_tag.has_attr("href") else "No link"
                else:
                    title = "No title"
                    link = "No link"
                authors_elem = div.find("div", class_="gs_a")
                year_elem = div.find("div", class_="gs_a")
                authors = authors_elem.get_text(strip=True) if authors_elem else "No authors"
                year = year_elem.get_text(strip=True) if year_elem else "No years"
                snippet_elem = div.find("div", class_="gs_rs")
                snippet = snippet_elem.get_text(strip=True) if snippet_elem else "No snippet"
                results.append(f"{idx+1}. {title}\nLink: {link}\nSnippet: {snippet}\nAuthors: {authors}\nYear: {year}")
            if not results:
                scraped = "No results found."
            else:
                scraped = "\n\n".join(results)
    except Exception as e:
        scraped = f"Exception during scraping: {e}"
    return {"scraped_data": scraped}

CLEANED_PROMPT = (
    "You are an expert in interpreting raw data scraped from Google Scholar. "
    "Please provide a cleaned JSON version of the data without typos or formatting errors. "
    "Change authors into lists and ensure the year is in the correct format. "
    "Keep the links intact."
)

USER_PROMPT = (
    "Clean the following raw data into proper JSON format:\n\n{scraped_data}"
)

def clean_scraped_data_node(state: AgentState):
    scraped = state.get("scraped_data", "")
    messages = [
        SystemMessage(content=CLEANED_PROMPT),
        HumanMessage(content=USER_PROMPT.format(scraped_data=scraped))
    ]
    response: AIMessage = model.invoke(messages)
    content = response.content
    start = content.find("```json") + len("```json")
    end = content.find("```", start)

    if start != -1 and end != -1:
        json_str = content[start:end].strip()
        cleaned_data = json.loads(json_str)  
    return {"cleaned_data": cleaned_data}


search_graph_agent = StateGraph(AgentState)
search_graph_agent.set_entry_point("scrape")
search_graph_agent.add_node("scrape", srape_scholar_papers_node)
search_graph_agent.add_node("clean", clean_scraped_data_node)
search_graph_agent.add_edge("scrape", "clean")
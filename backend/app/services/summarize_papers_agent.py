import os
import requests
from bs4 import BeautifulSoup
from typing import TypedDict, List
from langgraph.graph import StateGraph
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from langchain_groq import ChatGroq
from dotenv import load_dotenv
import json
from langchain_community.document_loaders import PyPDFLoader
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma
import random
import time

load_dotenv()
os.environ["TOKENIZERS_PARALLELISM"] = "false"  

model = ChatGroq(model_name="llama-3.3-70b-versatile", temperature=0.7)
embedding_model = HuggingFaceEmbeddings(model_name="BAAI/bge-small-en")

class AgentState(TypedDict):
    topic: str
    summarized_data: List[dict]

vectorstore = Chroma(collection_name="academic_papers", embedding_function=embedding_model)
retriever = vectorstore.as_retriever(search_type="similarity", search_kwargs={"k": 3})

def extract_relevant_sections(text: str) -> str:
    """
    If the text is short (< 3000 characters), return the entire text.
    If the text is very long (>= 3000 characters), try to extract sections that contain
    "abstract" and/or "conclusion". If at least one is found, return them with labels.
    Otherwise, return the first 3000 characters.
    """
    threshold = 3000
    if len(text) < threshold:
        return text

    lower_text = text.lower()
    abstract_index = lower_text.find("abstract")
    conclusion_index = lower_text.rfind("conclusion")

    extracted_abstract = ""
    extracted_conclusion = ""

    if abstract_index != -1:
        # Extract up to 1000 characters starting at "abstract"
        extracted_abstract = text[abstract_index:abstract_index + 1000].strip()
    if conclusion_index != -1:
        # Extract up to 1000 characters starting at "conclusion"
        extracted_conclusion = text[conclusion_index:conclusion_index + 1000].strip()

    if extracted_abstract or extracted_conclusion:
        result = ""
        if extracted_abstract:
            result += f"Abstract: {extracted_abstract}\n\n"
        if extracted_conclusion:
            result += f"Conclusion: {extracted_conclusion}"
        return result.strip()
    else:
        # If neither keyword is found, return the first threshold characters.
        return text[:threshold]

def scrape_papers_node(state: AgentState) -> AgentState:
    """Scrape and process each paper. Errors for individual links are caught so the chain continues."""
    papers = state["summarized_data"] or []
    session = requests.Session()
    
    common_headers = {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://scholar.google.com/",
        "Upgrade-Insecure-Requests": "1",
        "Connection": "keep-alive",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "same-origin"
    }
    user_agents = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.1 Safari/605.1.15"
    ]
    
    for paper in papers:
        url = paper.get("link")
        text = ""
        if not url:
            paper["content"] = "No URL provided"
            continue

        headers = common_headers.copy()
        headers["User-Agent"] = random.choice(user_agents)
        
        try:
            time.sleep(random.uniform(1, 3))
            response = session.get(url, headers=headers, timeout=10)
            final_url = response.url  
            
            if response.status_code != 200:
                text = f"Error: Received status code {response.status_code}"
            else:
                if final_url.lower().endswith(".pdf"):
                    try:
                        loader = PyPDFLoader(final_url)
                        pdf_text = "\n".join([page.page_content for page in loader.load()])
                        text = extract_relevant_sections(pdf_text)
                    except Exception as e:
                        text = f"Error loading PDF: {e}"
                else:
                    soup = BeautifulSoup(response.text, "html.parser")
                    for tag in soup.find_all(["header", "footer", "nav", "script", "style"]):
                        tag.decompose()
                    scraped_text = soup.get_text(separator="\n")
                    text = extract_relevant_sections(scraped_text)
        except Exception as e:
            text = f"Exception: {e}"
        
        try:
            vectorstore.add_texts([text], metadatas=[{"source": url}])
        except Exception as e:
            print(f"Error adding text to vectorstore: {e}")
        
        paper["content"] = text
    return {"summarized_data": papers}

SUMMARIZED_PROMPT = (
    "You are an expert in summarizing academic papers."
    "Summarize the provided content in a structured JSON format (compulsory) without typos or formatting errors. "
    "format:```json\n{\"authors\": [\"Author 1\", \"Author 2\"], \"summary\": \"Paper Summary\"}\n```"
)

USER_PROMPT = (
    "Summarize the following paper into a JSON format given in system prompt from the following information:\n\n"
    "Content: {content}\n"
    "Context: {context}\n"
)


def summarize_papers_node(state: AgentState):
    papers = state["summarized_data"]

    for paper in papers:
        retrieved_docs = retriever.invoke(paper["content"])
        retrieved_context = "\n\n".join([doc.page_content for doc in retrieved_docs]) if retrieved_docs else "No additional context found."
        messages = [
            SystemMessage(content=SUMMARIZED_PROMPT),
            HumanMessage(content=USER_PROMPT.format(content=paper["content"], context=retrieved_context))
        ]
        response: AIMessage = model.invoke(messages)
        content = response.content

        start = content.find("```json") + len("```json")
        end = content.find("```", start)

        if start != -1 and end != -1:
            json_str = content[start:end].strip()
            try:
                extracted = json.loads(json_str)
                paper["compared_authors"] = extracted.get("authors", [])
                paper["summary"] = extracted.get("summary", "")
                del paper["content"]
            except json.JSONDecodeError:
                paper["error"] = "Invalid JSON returned"
        else:
            paper["error"] = "No JSON found in response"

    return {"summarized_data": papers}

summarize_graph_agent = StateGraph(AgentState)
summarize_graph_agent.add_node("scrape", scrape_papers_node)
summarize_graph_agent.add_node("summarize", summarize_papers_node)
summarize_graph_agent.add_edge("scrape", "summarize")
summarize_graph_agent.set_entry_point("scrape")

# original_data = [
#     {
#         "title": "What is machine learning?",
#         "link": "https://link.springer.com/chapter/10.1007/978-3-319-18305-3_1",
#         "snippet": "A machine learning algorithm is a computational process that … This training is the “learning” part of machine learning. The … can practice “lifelong” learning as it processes new data and …",
#         "authors": [
#             "I El Naqa",
#             "MJ Murphy"
#         ],
#         "year": 2015
#     }
# ]
# graph = summarize_graph_agent.compile()

# initial_state = {
#     "topic": "Machine Learning",
#     "summarized_data": original_data
# }
# thread = {"configurable": {"thread_id": "1"}}
# for s in graph.stream(initial_state, thread):
#     print(s)

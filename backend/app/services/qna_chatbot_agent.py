import os
import json
from typing import TypedDict, List
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma
from langchain.chains import RetrievalQA
from langchain.memory import ConversationBufferMemory
from langchain_groq import ChatGroq
from langgraph.graph import StateGraph
from dotenv import load_dotenv

load_dotenv()
os.environ["TOKENIZERS_PARALLELISM"] = "false"

# Define the AgentState. It holds the topic name, list of papers, a current query,
# and a QnA history (which is a list of dicts with question/answer pairs).
class AgentState(TypedDict):
    topic: str            
    papers: List[dict] 
    query: str   
    qna_history: List[dict]  

llm = ChatGroq(model_name="llama-3.3-70b-versatile", temperature=0.7)
embedding_model = HuggingFaceEmbeddings(model_name="BAAI/bge-small-en")

def initialize_vectorstore(state: AgentState) -> Chroma:
    documents = []
    metadatas = []
    for paper in state.get("papers", []):
        doc_text = (
            f"Title: {paper.get('title','')}\n"
            f"Summary: {paper.get('summary','')}\n"
            f"Authors: {', '.join(paper.get('authors', []))}\n"
            f"Link: {paper.get('link','')}"
        )
        documents.append(doc_text)
        metadatas.append({"paper_id": paper.get("id", ""), "link": paper.get("link", "")})
    
    vectorstore = Chroma.from_texts(
        texts=documents,
        embedding=embedding_model,
        metadatas=metadatas,
        collection_name="academic_papers"
    )
    return vectorstore

def build_retrieval_qa_chain(state: AgentState, vectorstore: Chroma) -> RetrievalQA:
    retriever = vectorstore.as_retriever(search_type="similarity", search_kwargs={"k": 3})
    # qa_memory = ConversationBufferMemory(memory_key="chat_history", return_messages=True)
    qa_chain = RetrievalQA.from_chain_type(
        llm=llm,
        chain_type="stuff",  
        retriever=retriever,
        return_source_documents=True,
        # memory=qa_memory,
        output_key="result"   
    )
    return qa_chain

def qna_agent_node(state: AgentState) -> AgentState:
    """
    Process a user query by:
      1. (Re)initializing the vectorstore from the provided papers.
      2. Building a RetrievalQA chain with proper memory.
      3. Running the chain on a prompt that includes a system instruction and the user query.
      4. Appending the question–answer exchange to the qna_history in the AgentState.
    """
    vectorstore = initialize_vectorstore(state)
    qa_chain = build_retrieval_qa_chain(state, vectorstore)
    
    user_query = state["query"]
    
    system_prompt = (
        f"You are an expert on the topic '{state['topic']}' and are very patient and clear when explaining complex subjects. "
        "Answer the question below in simple, detailed language."
    )
    if len(state["qna_history"]) == 0:
        state["qna_history"].append({"role": "system", "content": system_prompt})
    
    result = qa_chain.invoke(user_query)
    state["qna_history"].append({"role": "user", "content": user_query})
    state["qna_history"].append({"role": "assistant", "content": result["result"]})
    return 

qna_graph_agent = StateGraph(AgentState)
qna_graph_agent.add_node("qna", qna_agent_node)
qna_graph_agent.set_entry_point("qna")

# if __name__ == "__main__":
#     topic_data = {
#         "topic": "eHMI",
#         "papers": [
#             {
#                 "title": "eHMI: Review and guidelines for deployment on autonomous vehicles",
#                 "link": "https://www.mdpi.com/1424-8220/21/9/2912",
#                 "id": "fde74d7c282947ed8b00db8d8b948a6b",
#                 "authors": ["C Guindel", "F Garcia", "Not Provided", "A De La Escalera", "J Carmona"],
#                 "summary": (
#                     "This paper reviews the current state of external human-machine interfaces (eHMIs) in autonomous vehicles, "
#                     "exploring their effectiveness in facilitating communication between vehicles and pedestrians, and presenting guidelines."
#                 )
#             },
#             {
#                 "title": "Survey of eHMI concepts: The effect of text, color, and perspective",
#                 "link": "https://www.sciencedirect.com/science/article/pii/S1369847819302293",
#                 "id": "c923d86e58eb47b2a00b7d687b9e0c87",
#                 "authors": ["Not Specified", "P Bazilinskyy", "D Dodou", "J De Winter"],
#                 "summary": (
#                     "This paper examines various eHMI concepts for autonomous vehicles based on crowdsourced surveys, "
#                     "highlighting that textual interfaces are clearer than non-textual ones."
#                 )
#             }
#         ],
#         "query": "What can you tell me about deploying eHMI on autonomous vehicles?",
#         "qna_history": [
#             {"role": "system", "content": "You are an expert on the topic 'eHMI' and are very patient and clear when explaining complex subjects. Answer the question below in simple, detailed language."},
#             {"role": "user", "content": "What are the main guidelines for deploying eHMI on autonomous vehicles?"},
#             {"role": "assistant", "content": "The main guidelines for deploying eHMI on autonomous vehicles are as follows: (1) Ensure that the interface is clearly visible and understandable to pedestrians, (2) Use a combination of text and color to convey information, (3) Consider the perspective of the viewer when designing the interface."}
#         ]
#     }
    
#     initial_state: AgentState = {
#         "topic": topic_data["topic"],
#         "papers": topic_data["papers"],
#         "query": topic_data["query"],
#         "qna_history": topic_data["qna_history"]
#     }
    
#     qna_graph = qna_graph_agent.compile()
#     output = qna_graph.invoke(initial_state)
#     print(output)
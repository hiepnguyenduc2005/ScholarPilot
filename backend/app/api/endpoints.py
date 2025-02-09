from fastapi import APIRouter, HTTPException, Query
from models.schema import TopicPost, PaperDelete, Paper, Topic, QueryInput
from db.firebase import db
from services.search_papers_agent import search_graph_agent
from services.summarize_papers_agent import summarize_graph_agent
from services.qna_chatbot_agent import qna_graph_agent
from uuid import uuid4

router = APIRouter()

@router.get("/")
def get_root():
    return {"message": "Welcome to ScholarPilot!"}

@router.get("/topics")
def get_topics():
    topics = db.collection("topics").get()
    topics = [topic.to_dict() for topic in topics]
    return {"topics": [f"{topic["title"]} - {topic["id"]}" for topic in topics]}

@router.post("/topics")
def initialize_topic(input: TopicPost):
    scraped_graph = search_graph_agent.compile()
    initial_state = {
        "topic": input.topic,
        "scraped_data": "",
        "cleaned_data": ""
    }
    scraped_state = scraped_graph.invoke(initial_state)
    summarize_graph = summarize_graph_agent.compile()
    before_summarize_state = {
        "topic": scraped_state["topic"],
        "summarized_data": scraped_state["cleaned_data"]
    }
    final_state = summarize_graph.invoke(before_summarize_state)
    id = uuid4().hex
    papers = []
    for paper in final_state["summarized_data"]:
        paper_id = uuid4().hex
        authors = list(set(paper.get("compared_authors", []) + paper.get("authors", [])))
        new_paper = Paper(id=paper_id, title=paper["title"], authors=authors, summary=paper["summary"], topic_id=id, link=paper["link"], year=paper["year"])
        papers.append(new_paper)
    topic = Topic(id=id, title=final_state["topic"], papers=papers, qna_history=[])
    db.collection("topics").document(id).set(topic.dict())
    saved_topic = db.collection("topics").document(id).get().to_dict()
    return {"topic": saved_topic}

@router.post("/topics/{topic_id}/qna")
def post_qna(topic_id: str, input: QueryInput):
    topic = db.collection("topics").document(topic_id).get().to_dict()
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found.")
    initial_state = {
        "topic": topic["title"],
        "papers": topic["papers"],
        "query": input.query,
        "qna_history": topic["qna_history"]
    }
    qna_graph = qna_graph_agent.compile()
    final_state = qna_graph.invoke(initial_state)
    # topic["qna_history"].append({"role": "user", "content": input.query})
    response = final_state["qna_history"][-1]["content"]
    # topic["qna_history"].append({"role": "assistant", "content": response})
    db.collection("topics").document(topic_id).set(topic)
    return {"response": response}


@router.get("/topics/{topic_id}")
def get_topic(topic_id: str):
    topic = db.collection("topics").document(topic_id).get().to_dict()
    # print(topic)
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found.")
    return {"topic": topic}

@router.delete("/topics/{topic_id}/papers/{paper_id}")
def remove_paper_from_topic(topic_id: str, paper_id: str):
    topic = db.collection("topics").document(topic_id).get().to_dict()
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found.")
    papers = topic["papers"]
    for paper in papers:
        if paper["id"] == paper_id:
            papers.remove(paper)
            break
    topic["papers"] = papers
    db.collection("topics").document(topic_id).set(topic)
    return {"topic": topic}
    

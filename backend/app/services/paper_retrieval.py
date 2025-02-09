# backend/app/services/paper_retrieval.py

def retrieve_papers(topic: str) -> list:
    # Simulated paper retrieval; in practice, use an API call.
    papers = []
    for i in range(5):
        papers.append({
            "id": i,
            "title": f"Paper {i} on {topic}",
            "abstract": "",  # Assume abstract might be missing.
            "url": f"https://example.com/paper{i}"
        })
    return papers

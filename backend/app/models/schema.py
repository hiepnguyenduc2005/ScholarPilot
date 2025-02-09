from pydantic import BaseModel
from typing import Literal

class TopicPost(BaseModel):
    topic: str

class QueryInput(BaseModel):
    query: str

class PaperDelete(BaseModel):
    topic_id: str
    paper_id: str

class Paper(BaseModel):
    id: str
    title: str
    authors: list[str]
    summary: str
    link: str
    year: int
    topic_id: str

class Message(BaseModel):
    role: Literal['system', 'assistant', 'user']
    content: str

class Topic(BaseModel):
    id: str
    title: str
    papers: list[Paper]
    qna_history: list[Message]

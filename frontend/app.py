import streamlit as st
import requests

base_url = 'http://localhost:8000/api'

if "topic_data" not in st.session_state:
    st.session_state.topic_data = None
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

st.title('ScholarPilot')
st.write("""
    Welcome to ScholarPilot! This is a tool that helps you find the best academic papers for your research.
    You can create a new topic or select an existing one, view the list of associated papers, and ask questions about the topic.
    """.strip())

st.header("Topic Management")
mode = st.radio("Choose an option:", ("Create New Topic", "Select Existing Topic"))

selected_topic_id = None

if mode == "Create New Topic":
    new_topic = st.text_input('Enter a topic query', key="new_topic_input")
    if st.button('Submit New Topic', key='new_topic_submit') and new_topic:
        if new_topic.lower() in [topic.split(' - ')[0].lower() for topic in requests.get(url=f"{base_url}/topics").json().get('topics', [])]:
            st.error("Topic already exists.")
        res_new = requests.post(url=f"{base_url}/topics", json={'topic': new_topic})
        if res_new.status_code == 200:
            data_new = res_new.json()
            st.success("Topic created!")
            selected_topic_id = data_new.get('topic', {}).get('id')
            res_topic = requests.get(url=f"{base_url}/topics/{selected_topic_id}")
            if res_topic.status_code == 200:
                st.session_state.topic_data = res_topic.json().get("topic", {})
                st.session_state.chat_history = st.session_state.topic_data.get("qna_history", [])
            else:
                st.error("Failed to fetch topic details after creation.")
        else:
            st.error("Failed to create topic.")
elif mode == "Select Existing Topic":
    res_list = requests.get(url=f"{base_url}/topics")
    if res_list.status_code == 200:
        topics_list = res_list.json().get('topics', [])
        if topics_list:
            topic_chosen = st.selectbox('Select a topic', topics_list)
            try:
                selected_topic_id = topic_chosen.split(' - ')[1]
            except IndexError:
                st.error("Invalid topic format. Expected format: 'Topic Title - topic_id'")
            else:
                if (st.session_state.topic_data is None or 
                    st.session_state.topic_data.get("id") != selected_topic_id):
                    res_topic = requests.get(url=f"{base_url}/topics/{selected_topic_id}")
                    if res_topic.status_code == 200:
                        st.session_state.topic_data = res_topic.json().get("topic", {})
                        st.session_state.chat_history = st.session_state.topic_data.get("qna_history", [])
                        st.session_state.chat_history = st.session_state.chat_history[1:]
                    else:
                        st.error("Failed to retrieve topic details.")
        else:
            st.warning("No topics found.")
    else:
        st.error("Error fetching topics.")

if st.session_state.topic_data:
    topic_data = st.session_state.topic_data
    st.header("Topic Details")
    st.subheader(f"Topic: {topic_data.get('title', 'Unknown')}")
    
    st.write("### Papers")
    papers = topic_data.get("papers", [])
    if papers:
        for paper in papers:
            col_left, col_right = st.columns([1, 2])
            with col_left:
                st.markdown(
                    f"<h4 style='margin: 0;'><a href='{paper.get('link','')}' target='_blank'>{paper.get('title','Untitled')}</a></h4>",
                    unsafe_allow_html=True
                )
                st.markdown(
                    f"<p style='margin: 0;'><strong>Authors:</strong> {', '.join(paper.get('authors', []))} ({paper.get('year', 'N/A')})</p>",
                    unsafe_allow_html=True
                )
                if st.button("Delete", key=f"delete_{paper.get('id')}"):
                    topic_id = topic_data.get("id")
                    delete_url = f"{base_url}/topics/{topic_id}/papers/{paper.get('id')}"
                    res_delete = requests.delete(delete_url)
                    if res_delete.status_code == 200:
                        st.success("Paper deleted! Reload for updated list.")
                    else:
                        st.error("Failed to delete paper.")
            with col_right:
                st.markdown(
                    f"<p style='margin: 0;'><strong>Summary:</strong> {paper.get('summary','No summary provided')}</p>",
                    unsafe_allow_html=True
                )
            st.write("---")
    else:
        st.write("No papers found for this topic.")

    st.write("### Ask a Question About This Topic")
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []
    
    for chat in st.session_state.chat_history:
        role = chat.get("role", "user")
        message = chat.get("content", "")
        st.chat_message(role).write(message)
    
    user_input = st.chat_input("Type your question here...")
    if user_input:
        st.chat_message("user").write(user_input)
        res_qna = requests.post(url=f"{base_url}/topics/{topic_data.get('id')}/qna", json={"query": user_input})
        if res_qna.status_code == 200:
            answer = res_qna.json().get("response", "No answer returned")
            st.chat_message("assistant").write(answer)
            st.session_state.chat_history.append({"role": "user", "content": user_input})
            st.session_state.chat_history.append({"role": "assistant", "content": answer})
        else:
            st.error("Error processing your question.")

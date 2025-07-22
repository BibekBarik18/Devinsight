import streamlit as st
import tempfile
import os
from main import graph,Command

st.title("Agentic AI code summarizer")

uploaded_file = st.file_uploader("Upload the file to summarize")
config = {"configurable": {"thread_id": "1"}}


if "state" not in st.session_state:
    st.session_state.state = None
if "config" not in st.session_state:
    st.session_state.config = config
if "edited_post" not in st.session_state:
    st.session_state.edited_post = ""
if "auto_resume_triggered" not in st.session_state:
    st.session_state.auto_resume_triggered = False


if st.button("Summarise"):
    if uploaded_file is not None:
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            temp_file.write(uploaded_file.read())
            temp_file_path = temp_file.name

        with st.spinner("Patience is the key to success"):
            st.session_state.state = graph.invoke(
                {"messages": temp_file_path},
                config=st.session_state.config
            )

        st.subheader("Developer summary")
        st.markdown(
            st.session_state.state["dev_summary"].content
        )

        st.subheader("Executive summary")
        st.markdown(
            st.session_state.state["executive_summary"].content
        )

        st.subheader("Tech Stack")
        st.markdown(
            st.session_state.state["tech_stack"].content
        )

        interrupt_message = st.session_state.state.get("__interrupt__")
        if interrupt_message:
            st.subheader("LinkedIn Post")
            st.session_state.edited_post =st.session_state.state["linkedin_post"].content
            st.text_area(
                "Edit the post below before sending it to Notion:",
                key="post_editor", 
                value=st.session_state.edited_post,
                height=400,
                on_change=lambda: st.session_state.update({"auto_resume_triggered": True})
            )

        os.remove(temp_file_path)

if st.session_state.auto_resume_triggered:
    st.session_state.auto_resume_triggered = False  
    with st.spinner("Posting to Notion..."):
        result = graph.invoke(
            Command(resume={"data": st.session_state.post_editor}),
            config=st.session_state.config
        )
        st.session_state.state = result

        if "Successfully" in result["messages"][-1].content:
            st.success("Posted to Notion successfully!")
        else:
            st.error("Something went wrong while posting to Notion.")
            st.text_area("Response from Notion", result["messages"][-1].content, height=300)

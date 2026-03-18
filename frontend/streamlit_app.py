import streamlit as st
import requests
import pandas as pd
import uuid

BACKEND_QUERY_URL = "http://localhost:8000/query"
BACKEND_METRICS_URL = "http://localhost:8000/metrics"

st.set_page_config(
    page_title="AI Data Copilot",
    page_icon="🤖",
    layout="wide"
)

st.title("🤖 AI Data Copilot")

if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

with st.sidebar:
    st.header("System Metrics")

    try:
        metrics_response = requests.get(BACKEND_METRICS_URL, timeout=10)
        if metrics_response.status_code == 200:
            metrics = metrics_response.json()
            st.metric("Total Queries", metrics["total_queries"])
            st.metric("Success Rate", metrics["success_rate"])
            st.metric("Avg Latency", metrics["avg_latency"])
        else:
            st.warning("Could not load metrics.")
    except Exception:
        st.warning("Metrics service unavailable.")

    st.divider()
    st.write("Session ID")
    st.code(st.session_state.session_id)

for msg in st.session_state.chat_history:
    if msg["role"] == "user":
        st.chat_message("user").write(msg["content"])
    else:
        with st.chat_message("assistant"):
            st.write(f"**Route:** {msg['route']}")
            st.write(msg["reasoning"])

            if msg["sql"]:
                st.subheader("💻 Generated SQL")
                st.code(msg["sql"], language="sql")

            if "sources" in msg and msg["sources"]:
                st.subheader("📚 Sources")
                st.write(", ".join(msg["sources"]))

            st.subheader("📊 Results")
            st.dataframe(msg["dataframe"], use_container_width=True)

            if msg["chart"]:
                chart = msg["chart"]
                if chart["chart_type"] == "bar":
                    st.subheader("📈 Chart")
                    st.bar_chart(msg["dataframe"].set_index(chart["x"])[chart["y"]])

question = st.chat_input("Ask a question about your data or documents")

if question:
    st.chat_message("user").write(question)

    st.session_state.chat_history.append({
        "role": "user",
        "content": question
    })

    payload = {
        "question": question,
        "session_id": st.session_state.session_id
    }

    with st.spinner("Analyzing..."):
        response = requests.post(BACKEND_QUERY_URL, json=payload, timeout=120)

    if response.status_code != 200:
        try:
            st.error(response.json()["detail"])
        except Exception:
            st.error(response.text)
        st.stop()

    result = response.json()
    df = pd.DataFrame(result["rows"], columns=result["columns"])

    assistant_message = {
        "role": "assistant",
        "route": result.get("route", "sql"),
        "reasoning": result["reasoning"],
        "sql": result.get("sql", ""),
        "dataframe": df,
        "chart": result.get("chart"),
        "sources": result.get("sources", [])
    }

    st.session_state.chat_history.append(assistant_message)

    with st.chat_message("assistant"):
        st.write(f"**Route:** {assistant_message['route']}")
        st.write(assistant_message["reasoning"])

        if assistant_message["sql"]:
            st.subheader("💻 Generated SQL")
            st.code(assistant_message["sql"], language="sql")

        if assistant_message["sources"]:
            st.subheader("📚 Sources")
            st.write(", ".join(assistant_message["sources"]))

        st.subheader("📊 Results")
        st.dataframe(df, use_container_width=True)

        if assistant_message["chart"]:
            chart = assistant_message["chart"]
            if chart["chart_type"] == "bar":
                st.subheader("📈 Chart")
                st.bar_chart(df.set_index(chart["x"])[chart["y"]])
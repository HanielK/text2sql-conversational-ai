import streamlit as st
import requests
import pandas as pd

BACKEND_URL = "http://localhost:8000/query"

st.set_page_config(
    page_title="AI Data Copilot",
    page_icon="🤖",
    layout="wide"
)

st.title("🤖 AI Data Copilot")

question = st.text_input(
    "Ask a question about your data",
    placeholder="Example: show total order amount by month"
)

if st.button("Run Query") and question:

    with st.spinner("Analyzing data..."):

        response = requests.post(
            BACKEND_URL,
            json={"question": question}
        )

        if response.status_code != 200:
            st.error(response.json()["detail"])
            st.stop()

        result = response.json()

    # ------------------------------------------------
    # Reasoning
    # ------------------------------------------------

    st.subheader("🧠 AI Reasoning")
    st.write(result["reasoning"])

    # ------------------------------------------------
    # Tables used
    # ------------------------------------------------

    st.subheader("🗂 Tables Used")
    st.write(", ".join(result["tables_used"]))

    # ------------------------------------------------
    # SQL
    # ------------------------------------------------

    st.subheader("💻 Generated SQL")
    st.code(result["sql"], language="sql")

    # ------------------------------------------------
    # Results table
    # ------------------------------------------------

    st.subheader("📊 Query Results")

    df = pd.DataFrame(result["rows"], columns=result["columns"])

    st.dataframe(df, use_container_width=True)

    # ------------------------------------------------
    # Auto Chart
    # ------------------------------------------------

    if result["chart"]:

        st.subheader("📈 AI Generated Chart")

        chart = result["chart"]

        x = chart["x"]
        y = chart["y"]

        st.bar_chart(df.set_index(x)[y])
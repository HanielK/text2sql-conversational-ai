import streamlit as st
import requests
import pandas as pd

# -----------------------------------------------------------
# CONFIG
# -----------------------------------------------------------

BACKEND_URL = "http://localhost:8000/query"

st.set_page_config(
    page_title="AI SQL Copilot",
    page_icon="🤖",
    layout="wide"
)

st.title("🤖 AI Data Copilot")
st.caption("Ask questions about your database in natural language.")

# -----------------------------------------------------------
# SESSION STATE
# -----------------------------------------------------------

if "history" not in st.session_state:
    st.session_state.history = []

# -----------------------------------------------------------
# INPUT
# -----------------------------------------------------------

question = st.text_input(
    "Ask a question about your data",
    placeholder="Example: show total order amount by month"
)

run_query = st.button("Run Query")

# -----------------------------------------------------------
# SEND REQUEST
# -----------------------------------------------------------

if run_query and question:

    with st.spinner("AI is analyzing your data..."):

        try:

            response = requests.post(
                BACKEND_URL,
                json={"question": question}
            )

            if response.status_code != 200:
                st.error(response.json()["detail"])
                st.stop()

            result = response.json()

        except Exception as e:
            st.error(f"Connection error: {e}")
            st.stop()

    # -------------------------------------------------------
    # DISPLAY RESULTS
    # -------------------------------------------------------

    st.subheader("🧠 AI Reasoning")
    st.write(result["reasoning"])

    st.subheader("🗂 Tables Used")
    st.write(", ".join(result["tables_used"]))

    st.subheader("💻 Generated SQL")
    st.code(result["sql"], language="sql")

    if result["was_self_corrected"]:
        st.warning("🔁 SQL was automatically corrected after an execution error.")

    # -------------------------------------------------------
    # SHOW RESULTS TABLE
    # -------------------------------------------------------

    st.subheader("📊 Query Results")

    if len(result["rows"]) == 0:
        st.info("Query executed successfully but returned no rows.")
    else:

        df = pd.DataFrame(result["rows"], columns=result["columns"])

        st.dataframe(
            df,
            use_container_width=True
        )

    # -------------------------------------------------------
    # STORE HISTORY
    # -------------------------------------------------------

    st.session_state.history.append({
        "question": question,
        "sql": result["sql"],
        "rows": len(result["rows"])
    })


# -----------------------------------------------------------
# HISTORY PANEL
# -----------------------------------------------------------

if st.session_state.history:

    st.sidebar.title("Query History")

    for item in reversed(st.session_state.history):

        st.sidebar.markdown(
            f"""
**Question:**  
{item['question']}

Rows Returned: {item['rows']}

---
"""
        )
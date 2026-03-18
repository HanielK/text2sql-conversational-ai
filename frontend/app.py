import streamlit as st
import requests
import pandas as pd
import uuid

API_URL = "http://localhost:8000"

st.set_page_config(layout="wide")

# --------------------------------------------------
# SESSION SETUP
# --------------------------------------------------

if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())

if "last_response" not in st.session_state:
    st.session_state.last_response = None

if "last_question" not in st.session_state:
    st.session_state.last_question = ""

session_id = st.session_state.session_id

# --------------------------------------------------
# STYLES
# --------------------------------------------------

st.markdown("""
<style>
button {
    background: linear-gradient(90deg, #5f9cff, #a64bf4);
    color: white;
}
</style>
""", unsafe_allow_html=True)

# --------------------------------------------------
# SIDEBAR
# --------------------------------------------------

st.sidebar.title("CGI AI Copilot")
page = st.sidebar.radio("Navigation", ["Home (Chat)", "Admin Console"])

# ==================================================
# 🟣 CHAT
# ==================================================

if page == "Home (Chat)":

    st.title("AI Orchestrator Chat")

    question = st.text_input("Ask a question", value=st.session_state.last_question)

    if st.button("Submit") and question:

        st.session_state.last_question = question

        with st.spinner("Processing your query..."):

            response = requests.post(
                f"{API_URL}/query",
                json={
                    "question": question,
                    "session_id": session_id
                }
            ).json()

            st.session_state.last_response = response

    response = st.session_state.last_response

    if response:

        if response.get("needs_clarification"):
            st.warning(response["clarification_question"])

        elif response.get("success"):

            st.subheader("Question Asked")
            st.write(response["question"])

            # -----------------------------
            # Confidence
            # -----------------------------
            confidence = response.get("confidence", 0)

            st.progress(min(max(confidence, 0), 1))
            st.caption(f"Confidence Score: {round(confidence, 2)}")

            if confidence < 0.6:
                st.error("⚠️ Low confidence — verify results")

            # -----------------------------
            # SQL
            # -----------------------------
            with st.expander("SQL Query"):
                st.code(response["sql"])

            # -----------------------------
            # Results
            # -----------------------------
            df = pd.DataFrame(
                response["result"]["rows"],
                columns=response["result"]["columns"]
            )

            st.subheader("Query Results")
            st.dataframe(df)

            # -----------------------------
            # Chart
            # -----------------------------
            chart = response.get("chart")

            if chart:
                st.subheader("Visualization")

                if chart["chart_type"] == "bar":
                    st.bar_chart(df.set_index(chart["x"])[chart["y"]])

                elif chart["chart_type"] == "line":
                    st.line_chart(df.set_index(chart["x"])[chart["y"]])

            # -----------------------------
            # Insights
            # -----------------------------
            st.subheader("Insights")
            st.info(response["insights"])

            # -----------------------------
            # Follow-ups
            # -----------------------------
            st.subheader("Follow-up Questions")

            for i, q in enumerate(response["follow_ups"]):
                if st.button(q, key=f"follow_{i}"):
                    st.session_state.last_question = q
                    st.session_state.last_response = None
                    st.rerun()

            # -----------------------------
            # Feedback
            # -----------------------------
            st.subheader("Was this helpful?")

            col1, col2 = st.columns(2)

            def send_feedback(rating):
                requests.post(
                    f"{API_URL}/feedback",
                    json={
                        "request_id": response["request_id"],
                        "session_id": session_id,
                        "question": response["question"],
                        "sql": response["sql"],
                        "plan": response["plan"],
                        "rating": rating,
                        "route": response["route"]
                    }
                )

            with col1:
                if st.button("👍"):
                    send_feedback("correct")
                    st.success("Feedback saved")

            with col2:
                if st.button("👎"):
                    send_feedback("incorrect")
                    st.warning("Feedback recorded")

            # -----------------------------
            # Golden Query
            # -----------------------------
            st.subheader("Promote to Golden Query")

            if st.button("⭐ Approve as Golden Query"):

                payload = {
                    "request_id": response["request_id"],
                    "session_id": session_id,
                    "question": response["question"],
                    "sql": response["sql"],
                    "plan": response["plan"],
                    "rating": "correct",
                    "comments": "Manual golden",
                    "route": response["route"],
                }

                res = requests.post(f"{API_URL}/feedback", json=payload)

                if res.status_code == 200:
                    st.success("Added to Golden Queries ✅")
                else:
                    st.error(res.text)

# ==================================================
# 🔵 ADMIN CONSOLE (UPGRADED)
# ==================================================

elif page == "Admin Console":

    st.title("📊 AI Performance Dashboard")

    # -----------------------------
    # Load Data
    # -----------------------------
    feedback = requests.get(f"{API_URL}/feedback").json()["items"]

    if not feedback:
        st.warning("No feedback yet")
        st.stop()

    df = pd.DataFrame(feedback)

    # -----------------------------
    # Extract confidence safely
    # -----------------------------
    def extract_conf(plan):
        if isinstance(plan, dict):
            return plan.get("confidence", 0)
        return 0

    df["confidence"] = df["plan"].apply(extract_conf)
    df["is_correct"] = df["rating"].apply(lambda x: 1 if x == "correct" else 0)

    # -----------------------------
    # KPIs
    # -----------------------------
    st.subheader("📈 Summary")

    col1, col2, col3 = st.columns(3)

    col1.metric("Total Queries", len(df))
    col2.metric("Accuracy", f"{df['is_correct'].mean():.2%}")
    col3.metric("Avg Confidence", f"{df['confidence'].mean():.2f}")

    # -----------------------------
    # Scatter Chart
    # -----------------------------
    st.subheader("📊 Confidence vs Accuracy")

    chart_df = df[["confidence", "is_correct"]]
    chart_df.columns = ["x", "y"]

    st.scatter_chart(chart_df)

    # -----------------------------
    # Risk Detection
    # -----------------------------
    st.subheader("🚨 Risky Queries (Low Confidence)")

    risky = df[df["confidence"] < 0.7]

    if not risky.empty:
        st.dataframe(risky[["question", "confidence", "rating"]])
    else:
        st.success("No risky queries 🎉")

    # -----------------------------
    # Recent Feedback
    # -----------------------------
    st.subheader("🧾 Recent Feedback")
    st.dataframe(df.sort_values(by="timestamp_utc", ascending=False).head(20))

    st.divider()

    # -----------------------------
    # Failures
    # -----------------------------
    st.subheader("❌ Failure Cases")

    failures = requests.get(f"{API_URL}/failures").json()["items"]

    for i, row in enumerate(failures):

        with st.expander(row.get("question", "Failure")):

            st.write("Error:", row.get("error"))
            st.code(row.get("sql", ""))

            if st.button(f"Replay Failure {i}"):

                replay = requests.post(
                    f"{API_URL}/query",
                    json={
                        "question": row.get("question"),
                        "session_id": session_id
                    }
                ).json()

                st.json(replay)

    st.divider()

    # -----------------------------
    # Golden Queries
    # -----------------------------
    st.subheader("⭐ Golden Queries")

    goldens = requests.get(f"{API_URL}/golden-queries").json()["items"]

    for i, g in enumerate(goldens):

        with st.expander(g["question"]):

            st.code(g["sql"])

            if st.button(f"Replay Golden {i}"):

                replay = requests.post(
                    f"{API_URL}/query",
                    json={
                        "question": g["question"],
                        "session_id": session_id
                    }
                ).json()

                st.json(replay)
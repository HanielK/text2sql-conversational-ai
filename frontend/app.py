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
# 🟣 TAB B — USER CHAT
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
                    "session_id": st.session_state.session_id
                }
            ).json()

            st.session_state.last_response = response

    response = st.session_state.last_response

    if response:

        # -----------------------------
        # Clarification
        # -----------------------------
        if response.get("needs_clarification"):
            st.warning(response["clarification_question"])

        elif response.get("success"):

            st.subheader("Question Asked")
            st.write(response["question"])

            # -----------------------------
            # Confidence + Alert
            # -----------------------------
            confidence = response.get("confidence", 0)

            st.progress(min(max(confidence, 0), 1))
            st.caption(f"Confidence Score: {round(confidence, 2)}")

            if confidence < 0.6:
                st.error("⚠️ Low confidence response — verify results or refine query.")

            # -----------------------------
            # SQL
            # -----------------------------
            with st.expander("SQL Query"):
                st.code(response["sql"])

            # -----------------------------
            # Table
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
                    st.experimental_rerun()

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
                        "session_id": st.session_state.session_id,
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
            # ⭐ Promote to Golden Query
            # -----------------------------
            st.subheader("Promote to Golden Query")

            if st.button("⭐ Approve as Golden Query"):
                send_feedback("correct")
                st.success("Added to Golden Queries ✅")


# ==================================================
# 🔵 TAB A — ADMIN CONSOLE
# ==================================================

elif page == "Admin Console":

    st.title("Admin Console")

    # -----------------------------
    # Metrics
    # -----------------------------
    st.subheader("System Metrics")

    metrics = requests.get(f"{API_URL}/metrics").json()

    col1, col2, col3 = st.columns(3)
    col1.metric("Total Queries", metrics["total_queries"])
    col2.metric("Success Rate", metrics["success_rate"])
    col3.metric("Avg Latency", metrics["avg_latency"])

    st.divider()

    # -----------------------------
    # Feedback
    # -----------------------------
    st.subheader("User Feedback")

    feedback = requests.get(f"{API_URL}/feedback").json()["items"]

    if feedback:
        df_feedback = pd.DataFrame(feedback)
        st.dataframe(df_feedback)

        if "confidence" in df_feedback.columns:

            st.subheader("Confidence Monitoring")

            avg_conf = df_feedback["confidence"].mean()
            st.metric("Average Confidence", round(avg_conf, 2))

            st.line_chart(df_feedback["confidence"])

            st.subheader("Low Confidence Queries (<0.6)")
            low_conf = df_feedback[df_feedback["confidence"] < 0.6]

            if not low_conf.empty:
                st.dataframe(low_conf)
            else:
                st.success("No low confidence queries 🎉")

    st.divider()

    # -----------------------------
    # Failures + Replay
    # -----------------------------
    st.subheader("Failure Cases")

    failures = requests.get(f"{API_URL}/failures").json()["items"]

    if failures:
        df_fail = pd.DataFrame(failures)

        for i, row in df_fail.iterrows():

            with st.expander(f"❌ {row.get('question')}"):

                st.write("Error:", row.get("error"))
                st.code(row.get("sql", ""))

                if st.button(f"Replay Query {i}"):

                    replay = requests.post(
                        f"{API_URL}/query",
                        json={
                            "question": row.get("question"),
                            "session_id": st.session_state.session_id
                        }
                    ).json()

                    st.subheader("Replay Result")
                    st.json(replay)

    st.divider()

    # -----------------------------
    # Golden Queries + Replay
    # -----------------------------
    st.subheader("Golden Queries")

    goldens = requests.get(f"{API_URL}/golden-queries").json()["items"]

    for i, g in enumerate(goldens):

        with st.expander(g["question"]):

            st.code(g["sql"])

            if st.button(f"Replay Golden {i}"):

                replay = requests.post(
                    f"{API_URL}/query",
                    json={
                        "question": g["question"],
                        "session_id": st.session_state.session_id
                    }
                ).json()

                st.json(replay)

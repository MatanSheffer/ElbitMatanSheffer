import streamlit as st
import pandas as pd
import traceback
from src.agent import ask

st.set_page_config(page_title="סוכן מידע גאוגרפי", page_icon="🛸", layout="wide")

st.markdown("""
<style>
    /* RTL layout for the entire app */
    .stApp, [data-testid="stAppViewContainer"] {
        direction: rtl;
    }
    /* Chat messages */
    [data-testid="stChatMessage"] {
        direction: rtl;
        text-align: right;
    }
    [data-testid="stChatMessageContent"] p,
    [data-testid="stChatMessageContent"] li {
        text-align: right;
    }
    /* Chat input */
    [data-testid="stChatInput"] textarea {
        direction: rtl;
        text-align: right;
    }
    /* Expanders */
    .streamlit-expanderHeader {
        direction: rtl;
        flex-direction: row-reverse;
    }
    /* Dataframe column headers */
    [data-testid="stDataFrame"] {
        direction: ltr;
    }
    /* Sidebar and general text */
    .stMarkdown p, .stMarkdown li {
        text-align: right;
    }
    /* Spinner text */
    [data-testid="stSpinner"] p {
        direction: rtl;
    }
    /* Buttons */
    .stButton button {
        direction: rtl;
    }
</style>
""", unsafe_allow_html=True)

st.title("🛸 סוכן מידע גאוגרפי - הגנה מפני פלישה")
st.markdown("שאל שאלות על הכוחות, היישובים וגבולות הגזרה בשפה חופשית.")


@st.cache_resource
def load_data():
    from src.database import init_db
    return init_db()


with st.spinner("טוען את בסיס הנתונים (זה עשוי לקחת כמה שניות)..."):
    try:
        conn = load_data()
    except Exception as e:
        st.error("שגיאה בטעינת קובץ הנתונים. ודא שהאקסל נמצא בנתיב הנכון.")
        st.error(str(e))
        st.code(traceback.format_exc())
        st.stop()

if "messages" not in st.session_state:
    st.session_state.messages = []

# Clear chat button
if st.session_state.messages:
    if st.button("🗑️ נקה שיחה"):
        st.session_state.messages = []
        st.rerun()

# Display chat history
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        if message.get("sql"):
            with st.expander("לצפייה בשאילתת SQL"):
                st.code(message["sql"], language="sql")
        if message.get("results_data"):
            with st.expander("לצפייה בנתונים גולמיים"):
                st.dataframe(pd.DataFrame(message["results_data"]), use_container_width=True)

# User input
if prompt := st.chat_input("לדוגמה: כמה חלליות מסוג ח7 יש לנו?"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("הסוכן חושב ומנתח את הנתונים..."):
            result = ask(prompt)

        st.markdown(result["answer"])

        if result.get("sql"):
            with st.expander("לצפייה בשאילתת SQL"):
                st.code(result["sql"], language="sql")

        results_data: list[dict] = result.get("results_data") or []
        if results_data:
            with st.expander("לצפייה בנתונים גולמיים"):
                df_res = pd.DataFrame(results_data)
                st.dataframe(df_res, use_container_width=True)

            df_map = pd.DataFrame(results_data)
            if "latitude" in df_map.columns and "longitude" in df_map.columns:
                st.subheader("תמונת מצב בשטח")
                st.map(df_map.rename(columns={"latitude": "lat", "longitude": "lon"}))

        st.session_state.messages.append({
            "role": "assistant",
            "content": result["answer"],
            "sql": result.get("sql"),
            "results_data": results_data,
        })

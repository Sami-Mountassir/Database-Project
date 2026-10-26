"""Wikipedia Time Machine - interface v0 (Streamlit).

Run from the repository root:
    python -m pip install streamlit PyMySQL
    python -m streamlit run ui/app.py
"""
import difflib
import os
import sys
from datetime import datetime, timezone
from pathlib import Path



import pymysql
import streamlit as st
import streamlit.components.v1 as components

sys.path.insert(0, str(Path(__file__).resolve().parent))
import queries  # noqa: E402

st.set_page_config(page_title="Wikipedia Time Machine", layout="wide")
st.title("Wikipedia Time Machine")
st.caption("Pick an article and a moment (UTC): see the page exactly as it was.")

with st.sidebar:
    st.header("Database")
    host = st.text_input("Host", os.environ.get("TM_HOST", "127.0.0.1"))
    port = st.number_input("Port", value=int(os.environ.get("TM_PORT", "3306")), step=1)
    user = st.text_input("User", os.environ.get("TM_USER", "bench"))
    password = st.text_input("Password", os.environ.get("TM_PASSWORD", "bench"), type="password")
    database = st.text_input("Database", os.environ.get("TM_DATABASE", "wikipedia_time_machine"))


def connect():
    return pymysql.connect(host=host, port=int(port), user=user, password=password,
                           database=database, connect_timeout=5)


try:
    connection = connect()
except Exception as error:  # show a readable message instead of a stack trace
    st.error(f"Cannot connect to MariaDB ({error}). Check the container is running and the sidebar settings.")
    st.stop()

try:
    with connection.cursor() as cursor:
        queries.set_utc(cursor)
        articles = queries.list_articles(cursor)
        if not articles:
            st.warning("The article table is empty. Load data first (see README Setup).")
            st.stop()
        labels = {f"{title} (id {article_id})": article_id for article_id, title in articles}
        article_id = labels[st.selectbox("Article", list(labels))]
        revisions = queries.list_revisions(cursor, article_id)
        first_start = revisions[0][2].replace(tzinfo=timezone.utc)
        last_start = revisions[-1][2].replace(tzinfo=timezone.utc)
        st.write(f"{len(revisions)} versions, from **{first_start:%Y-%m-%d %H:%M:%S} UTC** "
                 f"to **{last_start:%Y-%m-%d %H:%M:%S} UTC**.")

        mode = st.radio("Choose the moment by", ["Revision slider", "Exact date and time"], horizontal=True)
        if mode == "Revision slider":
            index = st.select_slider("Revision", options=list(range(len(revisions))),
                                     format_func=lambda i: f"{revisions[i][2]:%Y-%m-%d %H:%M} UTC", value=len(revisions) - 1)
            moment = revisions[index][2].replace(tzinfo=timezone.utc)
        else:
            day = st.date_input("Date (UTC)", value=last_start.date())
            clock = st.time_input("Time (UTC)", value=last_start.time().replace(microsecond=0))
            moment = datetime.combine(day, clock, tzinfo=timezone.utc)

        row = queries.article_as_of(cursor, article_id, moment)
        if row is None:
            st.info(f"This article did not exist yet at {moment:%Y-%m-%d %H:%M:%S} UTC "
                    f"(first version: {first_start:%Y-%m-%d %H:%M:%S} UTC).")
            st.stop()
        revision_id, title, content, author, revision_date = row
        st.subheader(title)
        st.caption(f"Revision {revision_id} by {author} - edited {revision_date:%Y-%m-%d %H:%M:%S} UTC")

        previous = None
        # previous version = the version valid just before this one started
        position = next((i for i, r in enumerate(revisions) if r[0] == revision_id), None)
        if position:
            before = revisions[position - 1][2].replace(tzinfo=timezone.utc)
            previous = queries.article_as_of(cursor, article_id, before)

        tab_text, tab_diff = st.tabs(["Content (wikitext)", "Changes vs previous version"])
        with tab_text:
            st.text_area("Wikitext", content or "", height=500, label_visibility="collapsed")
        with tab_diff:
            if previous is None:
                st.write("This is the first stored version: nothing to compare with.")
            else:
                html = difflib.HtmlDiff(wrapcolumn=80).make_table(
                    (previous[2] or "").splitlines(), (content or "").splitlines(),
                    f"revision {previous[0]}", f"revision {revision_id}", context=True, numlines=2)
                components.html(html, height=500, scrolling=True)
finally:
    connection.close()
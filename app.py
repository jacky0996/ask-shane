"""app.py — Streamlit 網頁介面(Phase 6)

跟 ask.py 同一套檢索 + 生成邏輯,只是換成網頁。
    streamlit run app.py
"""

import chromadb
import streamlit as st
from chromadb.utils import embedding_functions
from dotenv import load_dotenv
from google import genai
from google.genai import errors

import config
from ask import build_user_message, load_system_prompt, retrieve, stream_answer

load_dotenv()


@st.cache_resource
def get_resources():
    """載入一次就好:embedding 模型、向量庫、Gemini client、system prompt。"""
    if not config.CHROMA_DIR.exists():
        st.error("找不到知識庫,請先在終端機執行:python ingest.py")
        st.stop()
    ef = embedding_functions.SentenceTransformerEmbeddingFunction(model_name=config.EMBEDDING_MODEL)
    chroma = chromadb.PersistentClient(path=str(config.CHROMA_DIR))
    collection = chroma.get_collection(name=config.COLLECTION_NAME, embedding_function=ef)
    client = genai.Client()  # 自動讀環境變數 GEMINI_API_KEY
    system_prompt = load_system_prompt()  # 依 SHOW_SOURCES 決定是否暴露來源
    return collection, client, system_prompt


st.set_page_config(page_title="Ask Shane", page_icon="💬")
st.title("💬 Ask Shane")
st.caption("此為使用RAG的AI服務，使用自然語言，讓求才方能夠簡易的理解我。")

collection, client, system_prompt = get_resources()

question = st.text_input("想問什麼?", placeholder="例如:過往經歷?")

if question:
    hits = retrieve(collection, question)
    user_message = build_user_message(question, hits)

    with st.spinner("檢索文件並思考中…"):
        placeholder = st.empty()
        full = ""
        try:
            for text in stream_answer(client, system_prompt, user_message):
                full += text
                placeholder.markdown(full)
        except errors.APIError as e:
            st.error(f"呼叫 Gemini 出錯:{e}\n\n免費層偶爾高負載(503),稍等再試;若持續,檢查 GEMINI_API_KEY 與額度。")
            st.stop()

    # 開發模式才顯示來源與 debug 片段;對外模式(SHOW_SOURCES=false)隱藏。
    if config.SHOW_SOURCES:
        sources = list(dict.fromkeys(meta["source"] for _, meta in hits))
        st.divider()
        st.caption("📎 檢索到的來源:" + ", ".join(sources))
        with st.expander("看檢索到的原始片段(debug)"):
            for doc, meta in hits:
                st.markdown(f"**{meta['source']}**")
                st.text(doc)

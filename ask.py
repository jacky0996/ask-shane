"""ask.py — CLI 問答

流程:問題 → 向量檢索 top-k → 把片段組進 prompt → 呼叫 Claude → 串流輸出 + 附來源。
先確定 ingest.py 已經跑過(chroma_db/ 存在)。

    python ask.py
"""

import time

import chromadb
from chromadb.utils import embedding_functions
from dotenv import load_dotenv
from google import genai
from google.genai import errors, types

import config

load_dotenv()  # 從 .env 讀 GEMINI_API_KEY


def get_collection():
    if not config.CHROMA_DIR.exists():
        raise SystemExit("找不到知識庫,請先執行:python ingest.py")
    ef = embedding_functions.SentenceTransformerEmbeddingFunction(model_name=config.EMBEDDING_MODEL)
    client = chromadb.PersistentClient(path=str(config.CHROMA_DIR))
    return client.get_collection(name=config.COLLECTION_NAME, embedding_function=ef)


def retrieve(collection, question: str):
    """向量檢索:回傳最相關的 top-k chunk(documents + 來源 metadata)。"""
    res = collection.query(query_texts=[question], n_results=config.TOP_K)
    docs = res["documents"][0]
    metas = res["metadatas"][0]
    return list(zip(docs, metas, strict=False))


def build_user_message(question: str, hits) -> str:
    """把檢索到的片段組成 <context>,連同問題包成給 Claude 的訊息。"""
    parts = []
    for doc, meta in hits:
        parts.append(f"[來源:{meta['source']}]\n{doc}")
    context = "\n\n---\n\n".join(parts)
    return f"<context>\n{context}\n</context>\n\n問題:{question}"


def stream_answer(client, system_prompt: str, user_message: str, max_retries: int = 4):
    """呼叫 Gemini 串流生成,逐段 yield 文字。

    免費層偶爾回 503(高負載),在「還沒吐出任何文字」前做指數退避重試;
    若已經吐過字才失敗,就不重試(避免重複輸出),直接拋出。
    """
    for attempt in range(max_retries):
        produced = False
        try:
            stream = client.models.generate_content_stream(
                model=config.GEMINI_MODEL,
                config=types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    max_output_tokens=config.MAX_TOKENS,
                ),
                contents=user_message,
            )
            for chunk in stream:
                if chunk.text:  # 有些 chunk 沒有文字(例如只帶 metadata),跳過
                    produced = True
                    yield chunk.text
            return
        except errors.ServerError:
            if produced or attempt == max_retries - 1:
                raise
            time.sleep(2**attempt)


def answer(client, system_prompt: str, user_message: str):
    """呼叫 Gemini 並串流輸出答案(逐字印出)。"""
    for text in stream_answer(client, system_prompt, user_message):
        print(text, end="", flush=True)
    print()


# 對外模式(SHOW_SOURCES=false)時附加在 system prompt 後面的覆寫指令:
# 讓模型維持「只根據語料」的事實性,但不要在回答裡暴露任何檔名。
_NO_SOURCE_OVERRIDE = """

# 本次輸出模式(最終覆寫,優先於上面的引用規則)
- **不要**在回答中標註任何來源檔名,不得出現「(來源:…)」「來源:…」之類字樣,也不要在結尾列出來源清單。
- 其餘規則不變:你內部仍只能根據 <context> 提供的事實回答,查不到就誠實說不知道。只是「不顯示出處」而已。
"""


def load_system_prompt() -> str:
    """讀 system prompt;若是對外模式(SHOW_SOURCES=false),附加「不暴露來源」覆寫。"""
    sp = config.SYSTEM_PROMPT_PATH.read_text(encoding="utf-8")
    if not config.SHOW_SOURCES:
        sp += _NO_SOURCE_OVERRIDE
    return sp


def main():
    system_prompt = load_system_prompt()
    collection = get_collection()
    client = genai.Client()  # 自動讀環境變數 GEMINI_API_KEY

    print("Ask Shane — 認識林楨祥的問答機器人(輸入 q 離開)\n")
    while True:
        try:
            question = input("\n你想問什麼?> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n再見!")
            break
        if not question:
            continue
        if question.lower() in {"q", "quit", "exit"}:
            print("再見!")
            break

        hits = retrieve(collection, question)
        user_message = build_user_message(question, hits)

        print()
        try:
            answer(client, system_prompt, user_message)
        except errors.APIError as e:
            print(f"⚠️  呼叫 Gemini 出錯:{e}")
            print("   若是金鑰問題,請確認 .env 的 GEMINI_API_KEY 是否正確、額度是否足夠。")
            continue

        # 開發模式才顯示檢索到的來源(去重、保留順序),方便驗證 RAG 有沒有撈對;
        # 對外模式(SHOW_SOURCES=false)不顯示。
        if config.SHOW_SOURCES:
            sources = list(dict.fromkeys(meta["source"] for _, meta in hits))
            print(f"\n  📎 檢索到的來源:{', '.join(sources)}")


if __name__ == "__main__":
    main()

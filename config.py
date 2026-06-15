"""集中設定:語料路徑、模型、chunk / 檢索參數。

整個專案只有這裡放「可調參數」。改這裡就能調整行為,
不用動 ingest.py / ask.py 的邏輯。
"""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()  # 先載入 .env,讓底下能讀到 GEMINI_MODEL 等設定

# --- 路徑 ---
BASE_DIR = Path(__file__).parent
CORPUS_DIR = BASE_DIR / "corpus"  # 知識來源(profile.md + projects/**)
CHROMA_DIR = BASE_DIR / "chroma_db"  # 向量庫存放處(gitignore)
SYSTEM_PROMPT_PATH = BASE_DIR / "prompts" / "system.md"
COLLECTION_NAME = "ask_shane"

# --- Embedding(本地,免費,支援中文)---
# 預設用較小的多語模型(~470MB,首次下載快),不需要 query/passage 前綴。
# 想要更好的中文檢索品質可改成 "BAAI/bge-m3"(~2.3GB,較吃資源)。
EMBEDDING_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"

# --- 切塊(chunking)---
CHUNK_MAX_CHARS = 1200  # 每個 chunk 的大致上限(字元數)
CHUNK_OVERLAP_BLOCKS = 1  # chunk 之間重疊幾個段落,避免句子被切斷失去上下文

# --- 檢索 ---
TOP_K = 5  # 每次問答撈最相關的幾個 chunk 餵給 Claude

# --- Gemini(生成答案,免費層)---
# 模型可在 .env 用 GEMINI_MODEL 覆寫(換模型不用改程式);沒填就用預設。
# 免費層常見選擇:gemini-2.5-flash(穩定)、gemini-3.5-flash(較新、尖峰易 503)。
# key 到 https://aistudio.google.com/apikey 免費申請,填進 .env 的 GEMINI_API_KEY。
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
MAX_TOKENS = 2000  # 答案通常很短,2000 綽綽有餘(對應 max_output_tokens)


# --- 來源顯示開關(開發 vs 實際運用)---
# SHOW_SOURCES=true(預設):開發用。回答內文會標「(來源:xxx.md)」,介面也列出檢索到的來源,方便驗證 RAG。
# SHOW_SOURCES=false:實際給人用。回答不暴露任何檔名,介面也不顯示來源(模型內部仍只根據語料回答)。
# 在 .env 設定 SHOW_SOURCES=false 即可切成「對外」模式。
SHOW_SOURCES = os.getenv("SHOW_SOURCES", "true").strip().lower() in ("1", "true", "yes", "on")

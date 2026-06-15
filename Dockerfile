# Ask Shane — Streamlit RAG bot on Cloud Run
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    HF_HOME=/app/.hf_cache

WORKDIR /app

# 先裝相依(獨立成一層,利用 build cache)。
# torch 裝 CPU 版,避免抓進整包 CUDA(image 大、build 慢)。
COPY requirements.txt .
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu \
 && pip install --no-cache-dir -r requirements.txt

# 程式與語料
COPY config.py ingest.py ask.py app.py ./
COPY prompts/ ./prompts/
COPY corpus/ ./corpus/

# 在 build 階段就建好向量庫、並把 embedding 模型一起烤進 image,
# 讓容器冷啟動不必再下載(否則每次冷啟要抓 ~470MB 模型)。
RUN python ingest.py

# Cloud Run 會注入 PORT(預設 8080);Streamlit 綁 0.0.0.0、關掉互動式設定。
ENV PORT=8080
EXPOSE 8080
CMD streamlit run app.py \
    --server.port=${PORT} \
    --server.address=0.0.0.0 \
    --server.headless=true \
    --server.enableCORS=false \
    --server.enableXsrfProtection=false \
    --browser.gatherUsageStats=false

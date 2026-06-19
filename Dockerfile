# Ask Shane — dev image(本機 docker 跑用)。
# 單階段、簡單;Cloud Run 的 production image 請用 Dockerfile.prod。
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HF_HOME=/app/.hf_cache

WORKDIR /app

# torch 裝 CPU 版,避免抓進整包 CUDA。
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
 && pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu \
 && pip install --no-cache-dir -r requirements.txt

COPY . .

# 建知識庫(下載 bge-m3 ~2.3GB + 算 embedding)。本機 build 一次即可。
RUN python ingest.py

ENV PORT=8080
EXPOSE 8080

# --server.fileWatcherType=none:關掉熱重載 watcher(會誤觸 torchvision import 而崩潰)。
CMD streamlit run app.py \
    --server.port=${PORT} \
    --server.address=0.0.0.0 \
    --server.headless=true \
    --server.fileWatcherType=none \
    --browser.gatherUsageStats=false

# 部署到 Cloud Run(一次性設定)

> **流程**:開分支改 → 開 PR(GitHub Actions 跑 `ruff + pytest`)→ **分支保護擋著:CI 綠燈才准併 main** → 併進 main → **Cloud Run 內建的持續部署(Cloud Build)自己用 `Dockerfile.prod` build + 部署**。
>
> 分工:**GitHub Actions 只負責 CI 把關,部署交給 Cloud Run 原生 trigger。** 因為合併進 main 的前提是 CI 已綠,所以 main 上的部署等於被測試擋過了。

先設幾個變數(對齊服務名:`REGION=asia-east1`、`SERVICE=ask-shane`):

```bash
export PROJECT_ID=你的GCP專案ID
export REGION=asia-east1
gcloud config set project "$PROJECT_ID"
```

## 1. 啟用需要的 API

```bash
gcloud services enable \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  artifactregistry.googleapis.com \
  secretmanager.googleapis.com
```

## 2. 把 GEMINI_API_KEY 放進 Secret Manager(金鑰不進 git、不進 image)

```bash
printf '你的GeminiKey' | gcloud secrets create GEMINI_API_KEY --data-file=-
# 之後要換 key:
# printf '新key' | gcloud secrets versions add GEMINI_API_KEY --data-file=-
```

Cloud Run 服務的執行身分(預設 compute SA)要能讀這個 secret:

```bash
PROJECT_NUMBER=$(gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)')
gcloud secrets add-iam-policy-binding GEMINI_API_KEY \
  --member="serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"
```

## 3. 設定持續部署(Cloud Run → GitHub repo)

Cloud Run console → **建立服務 / 你的 `ask-shane` 服務 → 設定持續部署(Set up continuous deployment)**:

- **來源**:連結 GitHub,選 `你的帳號/ask-shane`,分支填 `^main$`(只在 main 部署,不在 PR)。
- **建置類型**:選 **Dockerfile**,並把 Dockerfile 路徑指到 **`Dockerfile.prod`**(Cloud Run 用的 production image;根目錄的 `Dockerfile` 是本機 dev 用的簡化版)。

設定後,每次有 commit 進 main,Cloud Build 會自動 build image 並部署新 revision。

> ⚠️ 這條 trigger **本身不跑測試**,把關靠的是下面第 5 步的分支保護(CI 沒綠就進不了 main)。兩者缺一不可。

## 4. 設定服務的 runtime 參數(記憶體 / env / secret)

⚠️ 這些是 **Cloud Run runtime 設定,`Dockerfile` 管不到**,要在服務上設一次(之後 trigger 重新部署會沿用,不會被打回預設):

```bash
gcloud run services update "$SERVICE" --region "$REGION" \
  --memory 4Gi --cpu 2 --cpu-boost \
  --allow-unauthenticated \
  --set-secrets GEMINI_API_KEY=GEMINI_API_KEY:latest \
  --set-env-vars SHOW_SOURCES=false,GEMINI_MODEL=gemini-2.5-flash
```

- **記憶體 4Gi**:embedding 模型用 **BAAI/bge-m3(~2.3GB 權重)**,加 torch + chroma + streamlit,載入峰值約 3G+。**2Gi 會不夠、512Mi 預設必 OOM**(畫面卡在 `Running get_resources()`)。(若改回小模型 MiniLM,2Gi 即可。)
- **`--cpu-boost`**:冷啟動載模型時臨時加 CPU,起得更快。
- 或從 console 改:服務 → 「編輯並部署新修訂版本」→ Container 分頁設 Memory / CPU / 環境變數 / Secret。

## 5. 設分支保護(「測試過才准併 main」)

這一步才是讓「CI 綠燈才合併」**真正成立**的關卡;沒設的話紅燈也能 merge,trigger 照樣部署。

`Settings → Branches → Add branch ruleset`(或 protect `main`):
- ✅ Require a pull request before merging
- ✅ Require status checks to pass → 勾選 **`lint-test`**(CI 的 job 名)

---

### 注意
- **冷啟動**:服務 scale-to-zero(沒人用不收費);第一個請求要載入 bge-m3(~2.3GB),約 20~40 秒。想避免可加 `--min-instances 1`(會持續計費)。
- **記憶體**:bge-m3 較大,設 `4Gi`;調太低會 OOM。
- **成本**:Cloud Run 有免費額度 + scale-to-zero;Gemini 走免費層。展示用幾乎零成本,但有額度/速率限制。
- **image 大小**:bge-m3 烤進 image(冷啟快),代價是 image 較大(~4GB+)、build 較久(下載 2.3GB 模型,約 8~12 分)。
- **部署路徑只留一條**:用 Cloud Run trigger 部署,所以 repo 沒有 `deploy.yml`;`.github/workflows/` 只剩 `ci.yml`(CI 把關)。別再另外加 GitHub Actions 部署,以免兩條搶著部署、互相覆蓋設定。

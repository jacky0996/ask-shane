# 部署到 Cloud Run(一次性設定)

> 流程:**開分支改 → 開 PR → CI(ruff + pytest)綠燈才准併 main → 併 main 自動部署 Cloud Run**。
> 你已會建專案 + 接 git,以下只補「啟用 API + secret + GitHub→GCP 授權(WIF)」這段。
> 先設好幾個變數(對齊 workflow:`REGION=asia-east1`、`SERVICE=ask-shane`):

```bash
export PROJECT_ID=你的GCP專案ID
export REGION=asia-east1
export GH_REPO=你的GitHubAccount/ask-shane   # owner/repo
gcloud config set project "$PROJECT_ID"
```

## 1. 啟用需要的 API

```bash
gcloud services enable \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  artifactregistry.googleapis.com \
  secretmanager.googleapis.com \
  iamcredentials.googleapis.com
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

## 3. 給「GitHub Actions 部署用」的服務帳號(SA)

```bash
gcloud iam service-accounts create gh-deployer --display-name="GitHub Actions deployer"
SA_EMAIL="gh-deployer@${PROJECT_ID}.iam.gserviceaccount.com"

for ROLE in roles/run.admin roles/cloudbuild.builds.editor \
            roles/artifactregistry.admin roles/iam.serviceAccountUser \
            roles/storage.admin; do
  gcloud projects add-iam-policy-binding "$PROJECT_ID" \
    --member="serviceAccount:$SA_EMAIL" --role="$ROLE"
done
```

## 4. Workload Identity Federation(讓 GitHub 免金鑰換取 GCP 憑證)

```bash
gcloud iam workload-identity-pools create github --location=global \
  --display-name="GitHub Actions"

gcloud iam workload-identity-pools providers create-oidc github \
  --location=global --workload-identity-pool=github \
  --display-name="GitHub OIDC" \
  --attribute-mapping="google.subject=assertion.sub,attribute.repository=assertion.repository" \
  --attribute-condition="assertion.repository=='${GH_REPO}'" \
  --issuer-uri="https://token.actions.githubusercontent.com"

# 只允許這個 repo 來扮演上面的 SA
gcloud iam service-accounts add-iam-policy-binding "$SA_EMAIL" \
  --role=roles/iam.workloadIdentityUser \
  --member="principalSet://iam.googleapis.com/projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/github/attribute.repository/${GH_REPO}"

# 取得要填到 GitHub secret 的 provider 字串
gcloud iam workload-identity-pools providers describe github \
  --location=global --workload-identity-pool=github --format='value(name)'
```

## 5. 在 GitHub 設 repo secrets

`Settings → Secrets and variables → Actions → New repository secret`,建三個:

| Secret | 值 |
|---|---|
| `GCP_PROJECT_ID` | 你的專案 ID |
| `GCP_SA_EMAIL` | `gh-deployer@<PROJECT_ID>.iam.gserviceaccount.com` |
| `GCP_WIF_PROVIDER` | 上面步驟 4 最後印出的 `projects/.../providers/github` |

## 6. 設分支保護(「測試過才准併 main」)

`Settings → Branches → Add branch ruleset`(或 protect `main`):
- ✅ Require a pull request before merging
- ✅ Require status checks to pass → 勾選 **`lint-test`**(CI 的 job 名)

這樣 PR 的 ruff/pytest 沒過就無法合併,合併後 `deploy.yml` 才會跑。

## 7. 第一次也可手動部署驗證(可選)

```bash
gcloud run deploy ask-shane --source . --region "$REGION" \
  --allow-unauthenticated --memory 2Gi --cpu 1 --timeout 600 \
  --set-secrets GEMINI_API_KEY=GEMINI_API_KEY:latest \
  --set-env-vars SHOW_SOURCES=false,GEMINI_MODEL=gemini-2.5-flash
```

部署完 gcloud 會印出服務網址(`https://ask-shane-xxxx.a.run.app`)。

---

### 注意
- **冷啟動**:服務 scale-to-zero(沒人用不收費);第一個請求要載入 embedding 模型,約 10~20 秒。想避免可加 `--min-instances 1`(會持續計費)。
- **記憶體**:torch + 模型需要,已設 `2Gi`;調太低會 OOM。
- **成本**:Cloud Run 有免費額度 + scale-to-zero;Gemini 走免費層。展示用幾乎零成本,但有額度/速率限制。
- **image 大小**:模型烤進 image(冷啟快),代價是 image 較大、build 較久(約 5~8 分)。

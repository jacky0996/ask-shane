# 本機 Jenkins (CD)

GitHub Actions 跑 CI(lint/test/typecheck),這台 Jenkins 跑 CD(build → push → deploy → smoke test)。

## 啟動

```bash
cd /Users/shane/Desktop/code/jenkins
docker compose up -d

# 拿初始 admin 密碼
docker exec jenkins cat /var/jenkins_home/secrets/initialAdminPassword
```

打開 http://localhost:8080,貼密碼,「Install suggested plugins」。

## 第一次設定要做的事

### 1. 裝必要 plugins
- **Docker Pipeline** — Jenkinsfile 內用 `docker` agent
- **Google Cloud SDK** — 用 gcloud 部署 Cloud Run(或直接走 shell)
- **GitHub Branch Source** — Multibranch pipeline 自動掃 PR/branch
- **Pipeline: Stage View** — UI 看 build 進度
- **Credentials Binding** — 把 GCP service account JSON 注入 build

### 2. 容器內安裝 gcloud(只做一次,持久化在 volume)

```bash
docker exec -it -u root jenkins bash

# 在容器內:
apt-get update && apt-get install -y curl apt-transport-https ca-certificates gnupg
curl https://packages.cloud.google.com/apt/doc/apt-key.gpg | apt-key add -
echo "deb https://packages.cloud.google.com/apt cloud-sdk main" > /etc/apt/sources.list.d/google-cloud-sdk.list
apt-get update && apt-get install -y google-cloud-cli docker.io
exit
```

### 3. 加 GCP service account 為 credential

1. GCP Console → IAM → Service Accounts → Create
   - 名字:`jenkins-cd`
   - Roles:`Artifact Registry Writer`、`Cloud Run Admin`、`Service Account User`
2. 給該 SA 一把 JSON key,下載
3. Jenkins → Manage Jenkins → Credentials → Add Credentials
   - Kind: **Secret file**
   - ID: `gcp-sa-key`
   - 上傳 JSON

### 4. 接 GitHub webhook

Pipeline / Multibranch 設定:
- Repository: 你的 GitHub repo URL
- 認證:用 PAT(GitHub → Settings → Developer settings → Personal access tokens)
- Webhook URL 給 GitHub:`http://你的公網IP:8080/github-webhook/`
- 本機開發可用 ngrok 暴露:`ngrok http 8080`

## 為什麼跑在本機

- **省錢**:免 GCE VM 月費 $15+
- **學習導向**:Jenkins 是給你練,不是給團隊用
- **CD 是低頻動作**:你不會一天 deploy 50 次,本機關機影響有限

正式要上線時的升級路徑:把 jenkins_home volume tar 起來丟到 GCE VM,docker compose up,即完成搬家。

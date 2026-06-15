# 服務 / GCP Project 對應表

每個服務獨立一個 GCP project,IAM 邊界對齊團隊邊界。

## 對應關係

| 服務 | GitHub Repo | GCP Project ID | Cloud Run Service | Artifact Registry Repo |
|---|---|---|---|---|
| Middle Platform(中台 / IdP) | [MiddlePlatform](https://github.com/jacky0996/MiddlePlatform) | `middleplatform-496708` | `middle-platform` | `middle-platform` |
| EDM Backend | [edm_backend](https://github.com/jacky0996/edm_backend) | `edmbackend` | `edm-backend` | `edm-backend` |
| EDM Frontend | [EDM](https://github.com/jacky0996/EDM) | `edmfront` | `edm-front` | `edm-front` |
| Job Digger API | [job-digger](https://github.com/jacky0996/job-digger)(?) | `jobdigger` | `job-digger` | `job-digger` |
| Job Digger Admin | [job_digger_admin](https://github.com/jacky0996/job_digger_admin) | `joberdiggeradmin` | `job-digger-admin` | `job-digger-admin` |
| Portfolio | — | (尚未開設) | — | — |

> **Region 統一**:`asia-east1`(台灣)
> **GitHub Owner**:`jacky0996`

## 命名慣例

- **GCP Project ID**:全小寫無底線,GCP 強制 6-30 字
  - middleplatform-496708 是因為 `middleplatform` 已被佔走,GCP 附加亂數
- **Cloud Run Service Name**:kebab-case,跟 AR repo 同名好記
- **Artifact Registry Repo**:跟 service name 同名

## 跨服務溝通(public URL)

部署後各 Cloud Run service 拿一個 `https://<name>-<hash>-de.a.run.app` 公網 URL。
中台的 JWKS endpoint 給其他服務拉:

```
https://middle-platform-<hash>-de.a.run.app/.well-known/jwks.json
```

各 Laravel 服務的 `SSO_JWKS_URL` env 填上即可。

## 跨 project IAM(Jenkins SA 需要做)

Jenkins SA 在 `jenkins-cd` 角色身份下,需要在**每個目標 project** 有以下 role:
- `roles/artifactregistry.writer`
- `roles/run.admin`
- `roles/iam.serviceAccountUser`
- `roles/secretmanager.secretAccessor`

執行範例(每個 project 跑一次):
```bash
for PROJECT in middleplatform-496708 edmbackend edmfront jobdigger joberdiggeradmin; do
  for ROLE in roles/artifactregistry.writer roles/run.admin roles/iam.serviceAccountUser roles/secretmanager.secretAccessor; do
    gcloud projects add-iam-policy-binding $PROJECT \
        --member="serviceAccount:jenkins-cd@<管理 SA 的 project>.iam.gserviceaccount.com" \
        --role=$ROLE
  done
done
```

> **重點**:Jenkins SA 本身屬於某個「管理 project」(建議用 middleplatform 那台,因為它最不會被淘汰),但要在所有目標 project 都被授權。

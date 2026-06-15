# EDM Frontend

Vue 3 + Vben Admin 5.0 打造的**電子郵件行銷 (EDM) 前端**。負責**活動 / 人員 / 群組管理 UI**、**邀請信編輯**、**Excel 大批匯入**,並作為 [Middle Platform](../Middle_Platform) SSO 的下游消費者(收到中台 redirect 帶來的 JWT 後,呼叫 [edm_backend](../edm_backend) 取資料)。

> ▸ **想直接跑起來** → 看 [sa-docs/deployment.md](./sa-docs/deployment.md)(`pnpm dev:ele` 或 `docker compose up -d --build`,host port 82) ▸ **想懂為什麼做** → 看 [sa-docs/overview.md](./sa-docs/overview.md)(SSO 客戶端 + 業務 UI 的雙重定位) ▸ **想理解架構** → 看 [sa-docs/architecture.md](./sa-docs/architecture.md)(分層 + Vben 結構 + 資料流 + SSO 序列) ▸ **想學怎麼操作** → 看 [sa-docs/user-guide.md](./sa-docs/user-guide.md)(End User 操作手冊) ▸ **想看流程圖** → 看 [sa-docs/user-flow.md](./sa-docs/user-flow.md)(SSO 進站 + 業務操作流程)

技術棧:Vue 3 (Composition API) / TypeScript / Vben Admin 5.0(pnpm Monorepo + Turborepo)/ Element Plus / Pinia / Vue Router 4 / Vite 5 / Axios / CKEditor 5 / ECharts / VXE Table / Docker 多階段 build + Nginx。

---

## SA 文件索引

本專案以 SA 視角整理文件,給三類讀者使用:

- **End User(行銷人員 / 業務)** — 想知道怎麼操作系統
- **開發者 / SA / Architect** — 想知道前端結構、跨系統整合
- **未來維護者** — 想知道某個技術決策當初的取捨

文件採 Markdown + Mermaid 撰寫,GitHub 直接渲染,不需要任何工具即可閱讀。

> **路徑說明**:本 repo 用 `sa-docs/` 而非 `docs/`,因為 `docs/` 是 Vben Admin 內建的 VitePress 文件站(`@vben/docs`),為避免結構衝突而獨立目錄。`sa-docs/` 命名也跟前端 SPA 內嵌的 `apps/web-ele/src/views/sa-docs/` 一致。

---

## 推薦閱讀順序

| # | 文件 | 給誰看 | 對應 UML 圖 |
| --- | --- | --- | --- |
| 1 | [sa-docs/overview.md](./sa-docs/overview.md) | 所有人 | — (純文字:定位 / Scope / Stakeholders / Roadmap) |
| 2 | [sa-docs/use-cases.md](./sa-docs/use-cases.md) | SA / PM / 開發者 | **Use Case Diagram**(4 個 Actor:活動管理員 / 業務 / 受邀者 / 系統) |
| 3 | [sa-docs/architecture.md](./sa-docs/architecture.md) | 開發者 / Architect | **Component Diagram** + **Sequence Diagram**(整體 / 前端技術棧 / 資料流 / SSO / 部署 五張圖) |
| 4 | [sa-docs/user-flow.md](./sa-docs/user-flow.md) | UX / 前端 / SA | **Activity Diagram** + **Sequence Diagram**(進站 → SSO redirect → 業務操作) |
| 5 | [sa-docs/api-integration.md](./sa-docs/api-integration.md) | 前端 / SA | — (Client 視角的整合契約;包含 SSO 隱身代理、X-User-Info header) |
| 6 | [sa-docs/deployment.md](./sa-docs/deployment.md) | Ops / Architect | **Deployment Diagram**(多階段 build + nginx + 跨容器網路) |
| 7 | [sa-docs/user-guide.md](./sa-docs/user-guide.md) | End User | — (操作手冊,非 UML) |
| 8 | [sa-docs/adr/](./sa-docs/adr/) | 後續維護者 | — (Architecture Decision Records) |

---

## SPA 內嵌 SA 文件頁(共存設計)

除了 `sa-docs/` 的 Markdown 正本,前端 SPA 內也有對應的 SA 文件頁面 — 登入後可在 EDM 系統內直接查看 Mermaid 互動圖:

| Vue 頁面 | 對應 Markdown 正本 |
| --- | --- |
| `apps/web-ele/src/views/sa-docs/architecture/index.vue` | [sa-docs/architecture.md](./sa-docs/architecture.md) |
| `apps/web-ele/src/views/sa-docs/use-case/index.vue` | [sa-docs/use-cases.md](./sa-docs/use-cases.md) |
| `apps/web-ele/src/views/sa-docs/requirement/index.vue` | [sa-docs/overview.md](./sa-docs/overview.md) |
| `apps/web-ele/src/views/sa-docs/api/index.vue` | [sa-docs/api-integration.md](./sa-docs/api-integration.md) |
| `apps/web-ele/src/views/sa-docs/er-diagram/index.vue` | (對應後端 [edm_backend/docs/data-model.md](../edm_backend/docs/data-model.md)) |

> **Markdown 是 source of truth**。Vue 頁面是內部 / Demo 用(讓登入的使用者也能看到 SA 文件),設計上應指向 GitHub markdown 為主,避免內容雙寫不同步。

---

## 不同角色的入口建議

| 你是誰 | 從這裡開始 |
| --- | --- |
| **第一次來** | `sa-docs/overview.md` → `sa-docs/architecture.md` → `sa-docs/use-cases.md` |
| **要 review 設計** | `sa-docs/use-cases.md` → `sa-docs/architecture.md` → `sa-docs/adr/` |
| **要串接後端 / 加新 API** | `sa-docs/api-integration.md` → 後端 [api-spec.md](../edm_backend/docs/api-spec.md) |
| **要處理 SSO 整合** | `sa-docs/user-flow.md` 第 1 節 → 中台 [user-flow.md](../Middle_Platform/docs/user-flow.md) |
| **要部署 / 維運** | `sa-docs/deployment.md` |
| **要學系統操作** | `sa-docs/user-guide.md` |

---

## 文件公約

- **圖優於文字**:盡量用 Mermaid 畫圖,文字補關鍵說明
- **每份文件 < 5 分鐘看完**:超過就拆檔
- **變更 code 時同步更新**:文件與 code 同 repo,改 router 就改 `architecture.md`,改 API client 就改 `api-integration.md`
- **決策必留 ADR**:任何「為什麼選 A 不選 B」的判斷,新增一份 ADR(模板見 [`sa-docs/adr/`](./sa-docs/adr/))
- **與中台 / 後端對齊**:本系統是 [Middle Platform](../Middle_Platform) + [edm_backend](../edm_backend) 生態的一份子,SA 文件結構與術語(Actor / IdP / SP / ADR)刻意三 repo 一致,讓跨 repo 閱讀體驗連貫
- **詞彙統一**:本文件統一稱「中台 (Middle Platform)」,程式碼與部分歷史文件可能仍稱「HWS」(內部代號),兩者指同一系統

---

## 近期變更

| 日期 | 變更 | 影響檔案 |
| --- | --- | --- |
| 2026-05-19 | `SurveyForm` 補上 開啟問卷 / 編輯問卷 / 解除綁定 三按鈕,並改為從 `getDisplayList` 載入綁定狀態 | [SurveyForm.vue](./apps/web-ele/src/views/event/detail/components/SurveyForm.vue) |
| 2026-05-19 | `EventAnalytics` 問卷區塊接 `getSurveyStats` 真實統計,圓餅圖中央顯示總填寫數,並提示邀請名單外填寫人數 | [EventAnalytics.vue](./apps/web-ele/src/views/event/detail/components/EventAnalytics.vue) |
| 2026-05-18 | 建立活動 / 活動詳細頁移除「活動橫幅」上傳區塊與預設圖 | [event/create/index.vue](./apps/web-ele/src/views/event/create/index.vue) · [event/detail/index.vue](./apps/web-ele/src/views/event/detail/index.vue) |
| 2026-05-18 | 表單 hook 移除 `img_url` / `bannerPreviewUrl` / 預覽 banner | [create/hooks/useForm.ts](./apps/web-ele/src/views/event/create/hooks/useForm.ts) · [detail/hooks/useDetailForm.ts](./apps/web-ele/src/views/event/detail/hooks/useDetailForm.ts) |
| 2026-05-18 | 活動詳細頁移除「設定」tab | [event/detail/index.vue](./apps/web-ele/src/views/event/detail/index.vue) |

對應後端變更見 [edm_backend README — 近期變更](../edm_backend/README.md#近期變更)。

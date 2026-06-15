# EDM Backend

Laravel 12 + PHP 8.2 打造的**電子郵件行銷 (EDM) 後端服務**。負責**會員 / 群組 / 活動管理**、**活動邀請信寄送**(AWS SES)、**Google Forms 問卷整合**,並作為 [Middle Platform](../Middle_Platform) SSO 的下游消費者(以 JWT 驗證身分)。

> ▸ **想直接跑起來** → 看 [docs/deployment.md](./docs/deployment.md)(`docker compose ... up -d --build` 一行)
> ▸ **想懂為什麼做** → 看 [docs/overview.md](./docs/overview.md)(系統定位 + Scope + Stakeholders)
> ▸ **想串接 API** → 看 [docs/api-spec.md](./docs/api-spec.md)(全部 endpoint + request/response 約定)
> ▸ **想了解架構** → 看 [docs/architecture.md](./docs/architecture.md)(分層 + Component / Class Diagram)
> ▸ **想理解資料表** → 看 [docs/data-model.md](./docs/data-model.md)(ERD)

技術棧:PHP 8.2 / Laravel 12 / MySQL 8.4 / Nginx / Docker Compose / Firebase JWT / AWS SES / Google API。

---

## SA 文件索引

本專案以 SA 視角整理文件,給三類讀者使用:

- **串接方(EDM 前端、其他服務)** — 想知道 API 怎麼呼叫
- **開發者 / SA / Architect** — 想知道系統長什麼樣、為什麼這樣設計
- **未來維護者** — 想知道某個技術決策當初的取捨

文件採 Markdown + Mermaid 撰寫,GitHub 直接渲染,不需要任何工具即可閱讀。

---

## 推薦閱讀順序

| # | 文件 | 給誰看 | 對應 UML 圖 |
|---|---|---|---|
| 1 | [docs/overview.md](./docs/overview.md) | 所有人 | — (純文字:動機 / Scope / Stakeholders) |
| 2 | [docs/architecture.md](./docs/architecture.md) | 開發者 / Architect | **Component Diagram** + **Class Diagram**(分層架構 + Eloquent 關聯) |
| 3 | [docs/data-model.md](./docs/data-model.md) | 開發者 / DBA | **ERD**(17 張表 + 欄位 + 索引) |
| 4 | [docs/api-spec.md](./docs/api-spec.md) | 串接方(EDM 前端) | — (HTTP contract,非 UML;補充 Scramble 自動產生的 Swagger UI) |
| 5 | [docs/sequence-diagrams.md](./docs/sequence-diagrams.md) | SA / 開發者 | **Sequence Diagram**(JWT 驗證、邀請信寄送、Google Form 同步) |
| 6 | [docs/deployment.md](./docs/deployment.md) | Ops / Architect | **Deployment Diagram**(Docker Compose × 3 layer) |
| 7 | [docs/adr/](./docs/adr/) | 後續維護者 | — (Architecture Decision Records) |

---

## 不同角色的入口建議

| 你是誰 | 從這裡開始 |
|---|---|
| **第一次來** | `docs/overview.md` → `docs/architecture.md` → `docs/sequence-diagrams.md` |
| **要 review 設計** | `docs/architecture.md` → `docs/data-model.md` → `docs/adr/` |
| **要串接 API** | `docs/api-spec.md` → Scramble Swagger UI(EdmBackend/docs/api) |
| **要部署 / 維運** | `docs/deployment.md` |
| **要查 DB schema** | `docs/data-model.md` |
| **要查 JWT 驗證細節** | `docs/sequence-diagrams.md` 第 1 節 + `docs/adr/0001-jwt-shared-secret.md` |

---

## 文件公約

- **圖優於文字**:盡量用 Mermaid 畫圖,文字補關鍵說明
- **每份文件 < 5 分鐘看完**:超過就拆檔
- **變更 code 時同步更新**:文件與 code 同 repo,改 model 就改 `data-model.md`,改 endpoint 就改 `api-spec.md`
- **決策必留 ADR**:任何「為什麼選 A 不選 B」的判斷,新增一份 ADR(模板見 [`docs/adr/`](./docs/adr/))
- **與中台對齊**:本系統是 [Middle Platform](../Middle_Platform) 生態的一份子,SA 文件結構與術語(Actor / IdP / SP / ADR)刻意與中台一致,讓跨 repo 閱讀體驗連貫

---

## 近期變更

| 日期 | 變更 | 影響 |
|---|---|---|
| 2026-05-20 | `member` 表新增 `creator_email` 欄位、`sales` 改名 `sales_email` | 對齊 controller 與 migration 預期,修正 `MemberController@editSales` 寫入失敗 |
| 2026-05-20 | `group` 表 `creator_enumber` 對齊改為 `creator_email` | 修正 `GroupController@create` 寫 `creator_email` 卻找不到 column 的問題 |
| 2026-05-20 | `member/list`、`group/list`、`event/list` 預設依 `X-User-Info.email` 過濾 | 進入這些功能時僅看到自己建立的資料 |
| 2026-05-20 | `MemberController@add` 改為自動記錄 `creator_email` 為當前登入者 | 配合 list 過濾機制 |
| 2026-05-20 | `EventRepository::GetList` 修正搜尋欄位 `name` → `title` | event 表沒有 `name` 欄位,前端搜尋從此能命中 |
| 2026-05-20 | `member/list`、`group/list`、`event/list` 的 `pageSize` 上限由 100 對齊到 200 | Vxe Grid 預設 `pageSizes: [...,200]`,使用者切到 200 即觸發 422「欄位驗證失敗」 |
| 2026-05-19 | 新增 `POST /api/edm/event/getSurveyStats` | 比對 `google_form_response.answers` 內 email 與 `event_relation`,提供邀請名單內/外填寫統計 |
| 2026-05-19 | `composer.json` 精簡 google-services 僅保留 `Forms` | vendor 從 ~100MB 砍到 ~1.1MB,移除 323 個未用 Google 服務 |
| 2026-05-19 | 修正 composer hook `Google\Task\Composer::cleanup` (原 `ComposerInformation` 為錯字) | 讓 `composer install` 真正執行精簡步驟 |
| 2026-05-18 | `event.creator_email` 補欄位 migration | 修正建立活動時 `Unknown column 'creator_email'` 錯誤 |
| 2026-05-18 | drop `event.img_url` 欄位 | 活動表單移除獨立的橫幅圖,內文插圖改由 CKEditor 內嵌處理 |
| 2026-05-18 | drop `event.creator_enumber` 欄位 | 建立者識別統一改用 `creator_email`,移除孤兒欄位 |
| 2026-05-18 | `EventController@create` / `@update` 不再寫 `img_url` | API request 不需傳 `img_url` |

對應 migration 檔位於 [`database/migrations/2026_05_18_*`](./database/migrations/)。

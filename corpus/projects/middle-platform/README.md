# Middle Platform

集中式身分識別與 SSO 中台服務。負責**簽發 JWT** 與**驗證 token**,作為多個業務系統(EDM、未來其他站)的共用登入中樞。
採 **Passwordless Magic Link**(Email 寄送一次性連結),不儲存密碼。

> ▸ **想直接跑起來** → 看 [docs/deployment.md](./docs/deployment.md)(`docker compose up -d` 一行,內含啟動/重置/常用指令)
> ▸ **想懂為什麼做** → 看 [docs/overview.md](./docs/overview.md)(LDAP 類比 + IdP 定位 + Scope)
> ▸ **想串接 API** → 看 [docs/api-spec.md](./docs/api-spec.md)
> ▸ **想了解架構** → 看 [docs/architecture.md](./docs/architecture.md)(C4 Model)

技術棧:Python 3.12 / Django 5.1 + DRF / SimpleJWT / MySQL 8 / Docker Compose。

---

## SA 文件索引

本專案以 SA 視角整理文件,給三類讀者使用:

- **使用者** — 想知道怎麼登入
- **開發者 / SA / Architect** — 想知道系統長什麼樣、為什麼這樣設計
- **未來維護者** — 想知道某個技術決策當初的取捨

文件採 Markdown + Mermaid 撰寫,GitHub 直接渲染,不需要任何工具即可閱讀。

---

## 推薦閱讀順序

| # | 文件 | 給誰看 | 對應 UML 圖 |
|---|---|---|---|
| 1 | [docs/overview.md](./docs/overview.md) | 所有人 | — (純文字:動機 / Scope / Glossary) |
| 2 | [docs/use-cases.md](./docs/use-cases.md) | SA / 開發者 / 審查者 | **Use Case Diagram** |
| 3 | [docs/user-flow.md](./docs/user-flow.md) | UX / 前端 / SA | **Activity Diagram** + **Sequence Diagram** |
| 4 | [docs/architecture.md](./docs/architecture.md) | 開發者 / Architect | **Component Diagram** + **Class Diagram** + **State Machine Diagram**(以 C4 Model 編排) |
| 5 | [docs/data-model.md](./docs/data-model.md) | 開發者 / DBA | **ERD** + **Class Diagram**(DB schema 視角) |
| 6 | [docs/api-spec.md](./docs/api-spec.md) | 串接方(EDM、其他子系統) | — (HTTP contract,非 UML) |
| 7 | [docs/deployment.md](./docs/deployment.md) | Ops / Architect | **Deployment Diagram** |
| 8 | [docs/user-guide.md](./docs/user-guide.md) | End User | — (操作手冊,非 UML) |
| 9 | [docs/adr/](./docs/adr/) | 後續維護者 | — (Architecture Decision Records) |

---

## 不同角色的入口建議

| 你是誰 | 從這裡開始 |
|---|---|
| **第一次來** | `docs/overview.md` → `docs/architecture.md` → `docs/user-flow.md` |
| **要 review 設計** | `docs/use-cases.md` → `docs/architecture.md` → `docs/adr/` |
| **要串接 API** | `docs/api-spec.md` → `docs/user-flow.md` 的 Sequence Diagram |
| **要部署 / 維運** | `docs/deployment.md` |
| **要查 DB schema** | `docs/data-model.md` |
| **要學登入操作** | `docs/user-guide.md` |

---

## 文件公約

- **圖優於文字**:盡量用 Mermaid 畫圖,文字補關鍵說明
- **每份文件 < 5 分鐘看完**:超過就拆檔
- **變更 code 時同步更新**:文件與 code 同 repo,改 model 就改 `data-model.md`,改 endpoint 就改 `api-spec.md`
- **決策必留 ADR**:任何「為什麼選 A 不選 B」的判斷,新增一份 ADR(模板見 [`docs/adr/`](./docs/adr/))

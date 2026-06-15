# Job Digger Admin

Laravel 11 後台,搭配 [`job-digger`](../job-digger) Python 爬蟲服務。**本專案只負責「設定關鍵字」與「檢視抓回的職缺」,不執行爬取**。整合 [Middle Platform](../Middle_Platform) SSO(Web Mode),使用者必須先通過中台登入才能進入。

> ▸ **想直接跑起來** → 看 [docs/deployment.md](./docs/deployment.md)(`docker compose up -d --build`,host port 8084)
> ▸ **想懂為什麼做** → 看 [docs/overview.md](./docs/overview.md)(系統定位、Stakeholders、Scope)
> ▸ **想理解 SSO 整合** → 看 [docs/sequence-diagrams.md](./docs/sequence-diagrams.md) 第 1 節 + [adr/0001-sso-web-mode.md](./docs/adr/0001-sso-web-mode.md)
> ▸ **想學怎麼操作** → 看 [docs/user-guide.md](./docs/user-guide.md)
> ▸ **想知道為什麼 APP_KEY 跟 SSO_JWT_SECRET 拆開** → 看 [adr/0003-app-key-vs-jwt-secret.md](./docs/adr/0003-app-key-vs-jwt-secret.md)(踩過的雷)

技術棧:PHP 8.2 / Laravel 11 / MariaDB(共用 job-digger 的 DB)/ Tailwind / Nginx + PHP-FPM(Docker)/ Firebase JWT(SSO 驗證)。

---

## SA 文件索引

本專案以 SA 視角整理文件,給三類讀者使用:

- **End User(我自己 / 行銷人員)** — 想知道怎麼用後台設關鍵字、看職缺
- **開發者 / SA / Architect** — 想知道架構、SSO 整合機制
- **未來維護者** — 想知道某個技術決策當初的取捨

文件採 Markdown + Mermaid 撰寫,GitHub 直接渲染,不需要任何工具即可閱讀。

---

## 推薦閱讀順序

| # | 文件 | 給誰看 | 對應 UML 圖 |
|---|---|---|---|
| 1 | [docs/overview.md](./docs/overview.md) | 所有人 | — (純文字:定位 / Scope / Stakeholders) |
| 2 | [docs/architecture.md](./docs/architecture.md) | 開發者 / Architect | **Component Diagram** + **Class Diagram**(MVC + Repository 分層 + SSO middleware) |
| 3 | [docs/data-model.md](./docs/data-model.md) | 開發者 / DBA | **ERD**(共用表 + 自有 users 表) |
| 4 | [docs/sequence-diagrams.md](./docs/sequence-diagrams.md) | SA / 開發者 | **Sequence Diagram**(SSO callback / 觸發爬蟲 / 列表查詢) |
| 5 | [docs/deployment.md](./docs/deployment.md) | Ops / Architect | **Deployment Diagram**(nginx + php-fpm + 連 host MariaDB) |
| 6 | [docs/user-guide.md](./docs/user-guide.md) | End User | — (操作手冊,非 UML) |
| 7 | [docs/adr/](./docs/adr/) | 後續維護者 | — (Architecture Decision Records) |

---

## 不同角色的入口建議

| 你是誰 | 從這裡開始 |
|---|---|
| **第一次來** | `docs/overview.md` → `docs/architecture.md` → `docs/sequence-diagrams.md` |
| **要 review 設計** | `docs/architecture.md` → `docs/data-model.md` → `docs/adr/` |
| **要 debug SSO** | `docs/sequence-diagrams.md` 第 1 節 → `adr/0001-sso-web-mode.md` → `adr/0003-app-key-vs-jwt-secret.md` |
| **要部署 / 維運** | `docs/deployment.md` |
| **要查 DB schema** | `docs/data-model.md` |
| **要學系統操作** | `docs/user-guide.md` 或 `/help` 頁(系統內) |

---

## 文件公約

- **圖優於文字**:盡量用 Mermaid 畫圖,文字補關鍵說明
- **每份文件 < 5 分鐘看完**:超過就拆檔
- **變更 code 時同步更新**:文件與 code 同 repo,改 middleware 就改 `architecture.md`,改 SSO 流程就改 `sequence-diagrams.md`
- **決策必留 ADR**:任何「為什麼選 A 不選 B」的判斷,新增一份 ADR
- **與生態系對齊**:本系統是 [Middle Platform](../Middle_Platform) + [job-digger](../job-digger) 生態的一份子,SA 文件結構與術語(Actor / IdP / SP / ADR)刻意跨 repo 一致

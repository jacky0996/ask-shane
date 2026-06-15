# Project Overview

本文件回答最根本的問題:**為什麼要做 Middle Platform?它在組織裡扮演什麼角色?**

---

## 1. 問題背景

當組織內有多個獨立的內部系統(EDM 行銷工具、未來其他業務系統)時,如果**每個系統各自實作登入**,會出現三個典型問題:

| 問題 | 後果 |
|---|---|
| **使用者要記多組帳密** | 體驗差,使用者用同一組弱密碼跨系統重用,風險集中 |
| **每個系統都要自己處理密碼安全** | 雜湊、防暴力、忘記密碼、密碼複雜度規則…重複工作 N 次,且容易做錯 |
| **改一次密碼要改 N 個地方** | 帳號生命週期管理失控,離職員工帳號清不乾淨 |

在 IT 治理上,這個情境的標準解法是設置一個**集中式身分提供者 (Centralized Identity Provider)**,所有業務系統把「驗證身分」這件事委外給它。

## 2. 設計類比 — 「Web 版的 LDAP」

Middle Platform 的角色,類比於企業內網裡的 **LDAP / Active Directory**:

```
            ┌─────────────────────────────────────────┐
            │   傳統企業內網 (1990s ~ )                  │
            │                                         │
            │   [Email]  [File Share]  [Intranet App] │
            │      │          │              │        │
            │      └──────────┼──────────────┘        │
            │                 ▼                       │
            │            [LDAP / AD]                  │
            │         (集中身分驗證)                     │
            └─────────────────────────────────────────┘

            ┌─────────────────────────────────────────┐
            │   現代 Web 服務 (本專案場景)                │
            │                                         │
            │   [EDM]    [其他業務系統]    [未來新站]      │
            │      │          │              │        │
            │      └──────────┼──────────────┘        │
            │                 ▼                       │
            │       [Middle Platform IdP]             │
            │         (集中身分驗證)                     │
            └─────────────────────────────────────────┘
```

**為什麼說是「類似 LDAP」而不是直接用 LDAP**:

| 面向 | LDAP | Middle Platform |
|---|---|---|
| 部署環境 | 企業內網 | Web / Cloud |
| 通訊協定 | LDAP protocol (TCP 389/636) | HTTP + JSON |
| 認證方式 | DN + 密碼 | Magic Link (Passwordless) |
| 信物 | LDAP Bind Session | JWT(無狀態,可帶離) |
| 業務系統怎麼用 | 每次請求 bind 一次 | 拿 JWT,自己 verify(不一定要回中台) |

**LDAP 是動機**(為什麼有這個系統:集中身分),**JWT / Magic Link 是實作**(用 web-friendly 的協定達成同樣目的)。

> 業界類似定位的產品:Auth0、Keycloak、Okta、AWS Cognito。本專案是這類產品的最小可運作版本(MVP),用來驗證設計思路,並作為 Portfolio 展示分散式架構與安全設計的能力。

## 3. Scope — 做什麼,不做什麼

### ✅ In Scope(本系統負責)

- **使用者身分管理**:Email 為唯一識別,passwordless 登入
- **登入信物簽發**:Magic Link 一次性連結 + JWT access token
- **Token 驗證 API**:供其他子系統(EDM 等)交換身分資訊
- **預設受保護**:Middleware 攔截未登入流量,白名單以外一律導回登入頁
- **管理介面**:Django Admin 供管理者檢視使用者與登入紀錄

### ❌ Out of Scope(本系統**不**負責)

- **業務資料**:訂單、活動、報表…全部歸各業務系統的 DB
- **權限細節 (Authorization)**:本系統只回答「你是誰 (Authentication)」,不回答「你能做什麼」。權限由各業務系統自行管理(本系統只透露 `is_staff` 等基本旗標)
- **第三方登入(Google / FB / SSO Federation)**:目前不支援,屬於未來 roadmap
- **多租戶 (Multi-tenant)**:預設單一組織

> **這條 Scope 線是面試或 review 時最常被質疑的地方。** 明確劃線可以避免「為什麼你的中台不做 X?」的質疑變成扣分,改成「我有意識地把 X 留在業務系統」的設計決定。

## 4. Stakeholders

| Stakeholder | 訴求 | 本系統如何回應 |
|---|---|---|
| **End User** | 不想記密碼、不想被打擾 | Passwordless,只要會收信即可登入 |
| **業務系統開發者** | 不想自己做登入、要簡單的 verify API | 提供 `/api/edm/sso/verify-token` (Vben 格式) 與 `/api/auth/verify-token/` (通用) |
| **管理者** | 要能查使用者、停用帳號、追登入紀錄 | Django Admin + `accounts_login_token` 留 IP 與時間 |
| **資安 / 稽核** | 不要存原始 token、要能追蹤 | LoginToken 只存 sha256 hash,所有狀態變更可追溯 |
| **Ops** | 要能水平擴展、可重啟不掉 session | JWT 無狀態,容器重啟不影響已登入使用者 |

## 5. 設計原則(Guiding Principles)

這五條原則貫穿所有設計決策,後續 ADR 都可以追溯到這幾條:

1. **Secure by default** — 所有 view 預設受保護,白名單明確列出例外([架構 Middleware 設計](./architecture.md#level-2--container-diagram容器服務組成))
2. **No password, no leak** — 不存密碼就不會洩密碼;不存原始 token 就不會洩 token([ADR-0001](./adr/0001-passwordless-magic-link.md)、[ADR-0003](./adr/0003-token-hash-only.md))
3. **Stateless verification** — 業務系統用 JWT 自己驗,不一定要回中台,降低中台負載([ADR-0002](./adr/0002-jwt-vs-session.md))
4. **Single responsibility** — 中台只管「你是誰」,不管「你能做什麼」
5. **Boring tech, simple stack** — Django + MySQL + Docker,團隊熟悉、社群成熟、容易維護

## 6. 非功能需求 (Non-Functional Requirements)

> 本專案為作品集 / Portfolio 性質,以下 NFR 是「設計時有考量」而非「壓測通過」的承諾。

| 類別 | 目標 | 設計回應 |
|---|---|---|
| **可用性** | 中台短暫不可用時,已登入使用者**不受影響** | JWT 無狀態,業務系統可用本地公鑰自驗(目前用 HS256,演進方向 RS256 → JWKS) |
| **安全性** | DB 外洩無法重放登入 | LoginToken 只存 hash;refresh token 黑名單機制 |
| **可觀測性** | 能追蹤誰、何時、從哪登入 | LoginToken 留 `created_ip` / `consumed_at`,可在 Admin 查 |
| **可演進** | Email 服務、業務系統可抽換 | Email Backend 是 Django 抽象層;業務系統間透過 HTTP + JWT,無耦合 |

## 7. Glossary

| 術語 | 中文 | 說明 |
|---|---|---|
| **IdP** (Identity Provider) | 身分提供者 | 提供身分驗證服務的系統,本專案的角色 |
| **SP** (Service Provider) | 服務提供者 | 消費 IdP 簽發信物的系統,EDM 在本架構是 SP |
| **Passwordless** | 無密碼登入 | 用「持有 Email」證明身分,而非「知道密碼」 |
| **Magic Link** | 魔法連結 | 一次性、有 TTL 的登入 URL,寄到使用者 Email |
| **JWT** (JSON Web Token) | — | 自帶簽章的字串,業務系統可自驗,免回中台查 |
| **OIDC** (OpenID Connect) | — | 業界 SSO 標準,本專案借用其概念但未完整實作 RFC |
| **ADR** (Architecture Decision Record) | 架構決策紀錄 | 一份決策一份檔,寫「為何選 A 不選 B」 |

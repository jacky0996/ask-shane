# API Specification

本文件列出 Middle Platform 對外提供的所有 HTTP endpoint,目標讀者:**串接方(EDM、未來其他子系統)、SA、QA**。

> 端對端的呼叫順序見 [`user-flow.md`](./user-flow.md) 的 Sequence Diagram。本文件聚焦於「單一 endpoint 的契約」。

---

## 1. 端點全覽

| 分類 | 方法 | 路徑 | 用途 | 認證 |
|---|---|---|---|---|
| **健康檢查** | GET | `/api/health/` | Liveness | 公開 |
| **SSO HTML 流程** | GET / POST | `/sso/login/` | 登入頁 / 寄 Magic Link | 公開 |
|  | GET / POST | `/sso/magic/<token>/` | 確認登入 / 核銷 Token | 公開(token 即憑證) |
|  | GET | `/sso/logout/` | 登出 | Session |
| **JWT 簽發 / 管理** | POST | `/api/auth/register/` | 程式化註冊(含密碼) | 公開 |
|  | POST | `/api/auth/login/` | 帳密登入取得 JWT | 公開 |
|  | POST | `/api/auth/refresh/` | 用 refresh 換新 access | 公開(帶 refresh) |
|  | POST | `/api/auth/logout/` | 把 refresh 加入黑名單 | JWT |
|  | GET | `/api/auth/me/` | 目前使用者資訊 | JWT |
| **Token 驗證** | POST | `/api/auth/verify-token/` | 通用 token 驗證 | 公開(帶 token) |
|  | POST | `/api/edm/sso/verify-token` | EDM 專用 (Vben 格式) | 公開(帶 token) |
| **Admin** | GET | `/admin/` | Django Admin | Superuser |

> Path 來源:[`config/urls.py`](../config/urls.py)、[`apps/accounts/urls.py`](../apps/accounts/urls.py)

---

## 2. 通用約定

### 2.1 Content Type

- 所有 POST 預設接 `application/json`(以及 `application/x-www-form-urlencoded` for SSO HTML 流程)
- 所有回應預設為 `application/json`(SSO HTML 流程除外,回 HTML)

### 2.2 認證方式

| 方式 | 標頭 | 用於 |
|---|---|---|
| **JWT Bearer** | `Authorization: Bearer <access_token>` | `/api/auth/me/`、`/api/auth/logout/` |
| **Token in body** | `{"token": "<jwt>"}` | `/api/auth/verify-token/`、`/api/edm/sso/verify-token` |
| **Session cookie** | Django session | SSO HTML 流程、`/admin/` |

### 2.3 錯誤格式

DRF 預設:

```json
{ "detail": "錯誤訊息" }
```

EDM 專用(Vben 格式):

```json
{ "code": 1, "message": "錯誤訊息", "data": null }
```

### 2.4 HTTP Status

| Status | 用法 |
|---|---|
| 200 | 成功 |
| 201 | 建立成功(register) |
| 205 | logout 成功(無 body) |
| 400 | 請求格式錯 |
| 401 | 認證失敗 |
| 410 | Magic Link 已過期 / 已使用 |

---

## 3. 各端點詳述

### 3.1 `GET /api/health/`

健康檢查,給 LB / K8s probe 用。

**Response 200**

```json
{ "status": "ok" }
```

---

### 3.2 `POST /api/auth/register/`

程式化註冊(含密碼),供需要密碼登入的場景使用。**SSO HTML 流程不會走這條**。

**Request**

```json
{
  "email": "user@example.com",
  "password": "ComplexPass123!",
  "display_name": "Alice"
}
```

**Response 201**

```json
{
  "email": "user@example.com",
  "display_name": "Alice"
}
```

**Errors**
- `400` `{"password": ["This password is too short..."]}` — Django 密碼驗證器
- `400` `{"email": ["user with this email already exists."]}`

---

### 3.3 `POST /api/auth/login/`

帳密登入,取得 access + refresh JWT。

**Request**

```json
{
  "email": "user@example.com",
  "password": "ComplexPass123!"
}
```

**Response 200**

```json
{
  "refresh": "eyJhbGciOiJIUzI1NiIs...",
  "access":  "eyJhbGciOiJIUzI1NiIs..."
}
```

**JWT Payload**(decode 後)

```json
{
  "token_type": "access",
  "exp": 1714500000,
  "iat": 1714498200,
  "jti": "uuid...",
  "user_id": 1,
  "email": "user@example.com",
  "display_name": "Alice"
}
```

**Errors**
- `401` `{"detail": "No active account found with the given credentials"}`

---

### 3.4 `POST /api/auth/refresh/`

用 refresh token 換新 access(及新 refresh,因 `ROTATE_REFRESH_TOKENS=True`)。

**Request**

```json
{ "refresh": "eyJhbGciOiJIUzI1NiIs..." }
```

**Response 200**

```json
{
  "refresh": "<新 refresh>",
  "access":  "<新 access>"
}
```

**Errors**
- `401` `{"detail": "Token is invalid or expired"}` — 包含已被 rotate 的舊 refresh

---

### 3.5 `POST /api/auth/logout/`

把 refresh token 加入黑名單,讓它立即失效。

**Headers**

```
Authorization: Bearer <access_token>
```

**Request**

```json
{ "refresh": "eyJhbGciOiJIUzI1NiIs..." }
```

**Response 205** — 無 body

**Errors**
- `400` `{"detail": "refresh token is required"}`
- `400` `{"detail": "Token is blacklisted"}` — 重複 logout

---

### 3.6 `GET /api/auth/me/`

取得目前 JWT 對應的使用者資訊。

**Headers**

```
Authorization: Bearer <access_token>
```

**Response 200**

```json
{
  "id": 1,
  "email": "user@example.com",
  "display_name": "Alice",
  "is_staff": false,
  "date_joined": "2026-04-25T10:00:00Z"
}
```

**Errors**
- `401` `{"detail": "Authentication credentials were not provided."}`

---

### 3.7 `POST /api/auth/verify-token/`

**通用** token 驗證,給其他子系統(非 EDM Vben 格式)使用。

**Request**(任一)

```json
{ "token": "<jwt>" }
```

或

```
Authorization: Bearer <jwt>
```

**Response 200**

```json
{
  "valid": true,
  "user": {
    "id": 1,
    "email": "user@example.com",
    "display_name": "Alice",
    "is_staff": false,
    "is_active": true
  }
}
```

**Errors**
- `400` `{"valid": false, "detail": "token is required"}`
- `401` `{"valid": false, "detail": "token_not_valid"}`

---

### 3.8 `POST /api/edm/sso/verify-token`

**EDM 專用** token 交換,回傳格式對齊 Vben Admin 模板。

> 同時提供帶尾斜線與不帶尾斜線兩條 path,因 Vben 預設不帶尾斜線。

**Request**

```json
{ "token": "<jwt>" }
```

> 也接受 `{"hws_token": "..."}`,為相容某些舊 client 的 key 命名。

**Response 200**

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "accessToken": "<原 token,原封不動回去>",
    "userInfo": {
      "userId": 1,
      "username": "user@example.com",
      "realName": "Alice",
      "email": "user@example.com",
      "roles": ["user"],
      "homePath": "/dashboard",
      "avatar": "",
      "desc": "SSO user from Middle Platform"
    }
  }
}
```

**roles 規則**:`is_superuser` → `["super"]`,其餘 → `["user"]`

**Errors**
- `400` `{"code": 1, "message": "token is required", "data": null}`
- `401` `{"code": 1, "message": "invalid token: ...", "data": null}`

---

### 3.9 `GET / POST /sso/login/`

SSO 登入入口頁(渲染 HTML)。

**GET 行為**
- 已登入 + 帶 `?redirect=<safe_url>` → 302 導去 `<safe_url>?token=<jwt>`
- 已登入 + 沒帶 redirect → 渲染 `login_success.html`(含 EDM 跳轉按鈕)
- 未登入 → 渲染 `login.html`(輸入 email)

**POST**
- Body: `email=<email>&redirect=<url>`(form-encoded)
- 寄出 magic link,渲染 `magic_link_sent.html`

**Errors**
- `400` 渲染 `login.html` 並顯示 「請輸入有效的 Email」

---

### 3.10 `GET / POST /sso/magic/<token>/`

Magic Link 核銷入口。**為何 GET 不直接登入**:Email 安全掃描器常會預抓所有連結,GET 直接核銷會讓未本人點擊也被消耗。所以:

- **GET**:渲染確認頁(`magic_link_confirm.html`),要求使用者按下「繼續登入」按鈕
- **POST**:才真正核銷 token、`is_active=True`、簽 JWT、302 導向 caller(或渲染 `login_success.html`)

**Errors**
- `404`:token_hash 找不到
- `410`:token 已過期 / 已被使用,渲染 `magic_link_invalid.html`

---

### 3.11 `GET /sso/logout/`

登出當前 session,302 導去 `?redirect=<safe_url>`(若有)或 `/sso/login/`。

> ⚠ 不會撤銷已簽出去的 JWT(JWT 是無狀態的),只清 Django session。要撤 JWT 請走 `/api/auth/logout/`。

---

## 4. 串接 Walkthrough(EDM 視角)

完整對話請見 [`user-flow.md` Sequence Diagram](./user-flow.md)。簡要版:

```
1. 使用者打開 EDM 首頁,EDM 發現沒 token
   → 302 到 http://middle-platform/sso/login/?redirect=http://localhost:82/

2. 使用者輸入 email,中台寄 Magic Link

3. 使用者收信點連結 → 中台確認頁 → 按下「登入」
   → 中台 302 到 http://localhost:82/sa-docs/uml?token=<JWT>

4. EDM 收到 ?token=...,POST 給中台:
   POST /api/edm/sso/verify-token  { "token": "<JWT>" }
   ← { "code": 0, "data": { "accessToken": ..., "userInfo": {...} } }

5. EDM 把 accessToken 存起來(localStorage / cookie),userInfo 灌進前端 store

6. EDM 之後呼叫 EDM 後端時,在 Authorization header 帶 JWT
   EDM 後端可以:
     (a) 自己 verify JWT 簽章(因為知道 SECRET_KEY,效能最佳)
     (b) 或回中台 POST /api/auth/verify-token/ (跨服務隔離,中台是唯一信任源)
```

---

## 5. 速率限制 / Rate Limiting

| 端點 | 機制 | 設定 |
|---|---|---|
| `/sso/login/` POST(寄信) | 同一 user 重寄冷卻 | `MAGIC_LINK_RESEND_COOLDOWN_SECONDS=60` |
| 其他端點 | **目前無** | Roadmap:加 django-ratelimit / nginx limit_req |

---

## 6. OpenAPI / Swagger

目前**未提供** OpenAPI YAML 自動產生,屬於 Roadmap。

備選方案:
- [`drf-spectacular`](https://drf-spectacular.readthedocs.io/) — 純 schema 自動產生,主流選擇
- [`drf-yasg`](https://drf-yasg.readthedocs.io/) — 較舊但仍維護
- 手寫 `openapi.yaml`(本文件已有所有資訊,可逐步補)

EDM 後端(Laravel)端的 API 已有 Swagger,中台補上後可在共同的 docs portal 串連。

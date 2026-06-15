# API Specification

本文件列出 EDM Backend 對外提供的所有 HTTP endpoint。目標讀者:**串接方(EDM 前端、其他內部服務)、SA、QA**。

> 互動式 Swagger UI 由 [Scramble](https://github.com/dedoc/scramble) 從 PHPDoc 自動產生,本機可在 EdmBackend/docs/api 查看(會帶可試打的 try-it-out 介面)。本文件聚焦於「設計層級」的契約與通用約定。

---

## 1. 端點全覽

所有 EDM API 以 `/api/edm` 為前綴,**統一使用 POST + JSON body**。路由定義於 [`routes/Api/edm.php`](../routes/Api/edm.php)。

| 分類 | 方法 | 路徑 | Controller | 說明 |
|---|---|---|---|---|
| **健康檢查** | GET | `/up` | (Laravel 內建) | Liveness |
| **API Docs** | GET | `/docs/api` | Scramble | Swagger UI |
| **Member** | POST | `/api/edm/member/list` | `MemberController@list` | 會員列表(分頁) |
|  | POST | `/api/edm/member/view` | `MemberController@view` | 會員詳細(含 emails / mobiles / organization) |
|  | POST | `/api/edm/member/add` | `MemberController@add` | 新增會員 |
|  | POST | `/api/edm/member/editStatus` | `MemberController@editStatus` | 修改 `member.status`(0/1) |
|  | POST | `/api/edm/member/editEmail` | `MemberController@editEmail` | 修改/新增/移除 member 的 email 關聯 |
|  | POST | `/api/edm/member/editMobile` | `MemberController@editMobile` | 修改/新增/移除 member 的 mobile 關聯 |
|  | POST | `/api/edm/member/editSales` | `MemberController@editSales` | 修改業務歸屬 (`sales_email`) |
| | | | | **list 預設依 `X-User-Info.email` 過濾,僅回傳當前登入者建立的會員 (`member.creator_email`)** |
| **Group** | POST | `/api/edm/group/list` | `GroupController@list` | 群組列表 |
|  | POST | `/api/edm/group/view` | `GroupController@view` | 群組詳細(含成員) |
|  | POST | `/api/edm/group/create` | `GroupController@create` | 建立群組(可一次帶成員) |
|  | POST | `/api/edm/group/editStatus` | `GroupController@editStatus` | 修改群組狀態 |
|  | POST | `/api/edm/group/getEventList` | `GroupController@getEventList` | 該群組曾參與的活動清單 |
| | | | | **list 預設依 `X-User-Info.email` 過濾,僅回傳當前登入者建立的群組 (`group.creator_email`)** |
| **Event** | POST | `/api/edm/event/list` | `EventController@list` | 活動列表 (依 `X-User-Info.email` 過濾) |
|  | POST | `/api/edm/event/view` | `EventController@view` | 活動詳細 |
|  | POST | `/api/edm/event/create` | `EventController@create` | 建立活動(自動產生 `event_number = B<seq>`) |
|  | POST | `/api/edm/event/update` | `EventController@update` | 更新活動 |
|  | POST | `/api/edm/event/imageUpload` | `EventController@imageUpload` | 上傳活動內文插圖(供 CKEditor 內嵌使用,不再寫入獨立的橫幅欄位) |
|  | POST | `/api/edm/event/getImage` | `EventController@getImage` | 取得活動圖片 |
|  | POST | `/api/edm/event/getInviteList` | `EventController@getInviteList` | 取得邀請名單(Event ↔ Member 透過 EventRelation) |
|  | POST | `/api/edm/event/importGroup` | `EventController@importGroup` | 從群組匯入邀請對象到 EventRelation |
|  | POST | `/api/edm/event/getDisplayList` | `EventController@getDisplayList` | 上架活動列表(`is_display=1`) |
|  | POST | `/api/edm/event/updateDisplay` | `EventController@updateDisplay` | 切換 `is_display` |
|  | POST | `/api/edm/event/createGoogleForm` | `EventController@createGoogleForm` | 為活動建 Google Form |
|  | POST | `/api/edm/event/updateGoogleForm` | `EventController@updateGoogleForm` | 更新表單設定 |
|  | POST | `/api/edm/event/delGoogleForm` | `EventController@delGoogleForm` | 解除綁定 / soft delete |
|  | POST | `/api/edm/event/getGoogleForm` | `EventController@getGoogleForm` | 取得綁定的 form 與其 responses |
|  | POST | `/api/edm/event/updateResponseStatus` | `EventController@updateResponseStatus` | 審核 GoogleFormResponse(0/1/2) |
|  | POST | `/api/edm/event/getSurveyStats` | `EventController@getSurveyStats` | 取得活動問卷填寫統計(邀請名單內/外比對) |
| **Mail** | POST | `/api/edm/mail/inviteMail` | `MailController@inviteMail` | 觸發批次寄送邀請信(Job 隊列) |

> 完整路由列表(含 system route)可在容器內執行 `php artisan route:list` 取得。

---

## 2. 通用約定

### 2.1 認證 — JWT Bearer

所有 `/api/edm/*` endpoint **應該** 走 `AuthorizeJwt` middleware。

```
Authorization: Bearer <jwt_signed_by_middle_platform>
```

中台用 `APP_KEY` (HS256) 簽 JWT,EDM Backend 用同一把 key 解碼。詳見 [adr/0001-jwt-shared-secret.md](./adr/0001-jwt-shared-secret.md) 與 [`sequence-diagrams.md` 第 1 節](./sequence-diagrams.md#1-jwt-驗證流程)。

> ⚠ **目前狀態**:`routes/Api/edm.php` 中 `AuthorizeJwt::class` middleware 被註解掉(僅本機開發方便),**正式部署必須開啟**。

### 2.2 Content Type

- Request:`application/json`(Body 全用 JSON)
- Response:`application/json`

### 2.3 Request Body 慣例

所有 endpoint 接 POST + JSON,常見欄位:

```json
{
  "id": 123,                  // 單筆操作的目標 ID
  "page": 1,                  // 列表分頁
  "per_page": 20,
  "filters": { "...": "..." } // 列表過濾
}
```

### 2.4 Response Format

**成功**

```json
{
  "code": 0,
  "message": "ok",
  "data": { /* 業務資料 */ }
}
```

**列表**

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "items": [ /* ... */ ],
    "total": 123,
    "page": 1,
    "per_page": 20
  }
}
```

**錯誤**

```json
{
  "code": 1,
  "message": "錯誤描述",
  "data": null
}
```

> 此格式對齊 EDM 前端(Vben)預期的回應 schema,跟中台 `/api/edm/sso/verify-token` 一致(見 [Middle Platform api-spec.md 3.8](../../Middle_Platform/docs/api-spec.md#38-post-apiedmssoverify-token))。

### 2.5 HTTP Status Code

| Status | 用法 |
|---|---|
| 200 | 成功 |
| 401 | JWT 缺失 / 過期 / 簽章不對 |
| 403 | IP 不在白名單(`WhitelistIpMiddleware`) |
| 404 | 資源不存在 |
| 422 | Validation 失敗(Laravel `FormRequest`) |
| 500 | 未捕捉的 server error |

---

## 3. 各端點詳述(精選)

> **完整 schema 以 Scramble 自動產生的 OpenAPI 為準**(EdmBackend/docs/api)。本節列幾個關鍵 endpoint 的設計說明。

### 3.1 `POST /api/edm/event/create`

**Request**

```json
{
  "title": "2026 新品發表會",
  "summary": "...",
  "content": "<p>HTML rich text</p>",
  "start_time": "2026-05-01 14:00:00",
  "end_time": "2026-05-01 17:00:00",
  "address": "台北市信義區...",
  "landmark": "信義誠品",
  "type": 1,
  "status": 1,
  "creator_email": "user@example.com"
}
```

**Response 200**

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "id": 42,
    "event_number": "B000042",   // 由 document_count 自動產生
    "title": "2026 新品發表會",
    /* ... */
  }
}
```

**設計重點**

- `event_number` 不由 client 提供,由 server 從 `document_count` 取下一個流水號
- 建立時 `is_approve` / `is_display` / `is_qrcode` 預設 `0`,需另外經審核流程才上架

### 3.2 `POST /api/edm/event/importGroup`

把整個 Group 的成員一次匯入 Event 的邀請清單(寫進 `event_relation`)。

**Request**

```json
{
  "event_id": 42,
  "group_ids": [1, 2, 3]
}
```

**行為**

1. 查 `has_group` 取出每個 group 的 member ids
2. 對每個 member,**snapshot** 它當下的 primary email_id / mobile_id / organization_id 寫進 `event_relation`
3. 已存在的 (event_id, member_id) 跳過(冪等)

**Response 200**

```json
{
  "code": 0,
  "data": {
    "imported": 187,
    "skipped_existing": 3,
    "total_in_groups": 190
  }
}
```

### 3.3 `POST /api/edm/mail/inviteMail`

對某 event 的所有邀請對象批次寄發邀請信。**非同步**,實際寄送由 Worker 從 `jobs` 表撈 Job 執行。

**Request**

```json
{
  "event_id": 42,
  "subject": "【華電聯網】您受邀參加 2026 新品發表會",
  "body_template": "<p>Dear {name}, ...</p>",
  "from": "noreply@example.com"
}
```

**行為**

1. 查 `event_relation WHERE event_id = ? AND deleted_at IS NULL` 取得邀請名單
2. join `email` table 取每個 EventRelation 凍結的 `email_id`
3. **chunk by 100**,每 chunk 派一個 `SendAwsMailJob` 進 queue
4. 立即回 200(實際寄送非同步)

**Response 200**

```json
{
  "code": 0,
  "data": {
    "queued": 187,
    "chunks": 2
  }
}
```

> Worker 從 `jobs` 表撈出後,呼叫 `AwsSesService::sendBatch()`,失敗會進 `failed_jobs` 表。詳見 [`sequence-diagrams.md` 第 2 節](./sequence-diagrams.md#2-寄送活動邀請信)。

### 3.4 `POST /api/edm/event/createGoogleForm`

為 event 建立一張 Google Form。

**行為**

1. 呼叫 `GoogleApiService::createForm()` 透過 `google/apiclient` 建立表單
2. 把 `form_id` / `form_url` 寫進 `google_form` 表
3. (可選)初始化 `google_form_stats` 一筆

**Roadmap**:目前 form schema 是 hard-coded,未來支援從 `event_template` 套用模板。

### 3.5 `POST /api/edm/event/getSurveyStats`

取得活動的問卷填寫統計，用於活動數據儀表板的圓餅圖。

**Request**

```json
{
  "event_id": 42
}
```

**Response 200**

```json
{
  "code": 0,
  "status": true,
  "data": {
    "has_google_form": true,
    "total_invited": 187,
    "filled_invited": 92,
    "unfilled_invited": 95,
    "non_invited_responses": 4,
    "total_responses": 96
  }
}
```

**比對規則**

1. `total_invited` — `event_relation` 內 `email_id` 可 join 到 `email.email` 的不重複 email 數量
2. 從 `google_form_response.answers` 找出標題為「電子郵件」/「email」/「e-mail」/「gmail」的答案，或符合 RFC email 格式者
3. `filled_invited` — 填寫者 email ∈ 邀請清單 的人數(去重)
4. `non_invited_responses` — 填寫者 email ∉ 邀請清單 (含無法解析 email)
5. `unfilled_invited` = `total_invited` − `filled_invited`

**邊界情境**

- 活動尚未綁定 Google 表單：`has_google_form=false`、`total_responses=0`、`unfilled_invited=total_invited`
- 邀請名單為空：所有計數歸 0，僅 `non_invited_responses` 可能有值

### 3.6 `POST /api/edm/event/updateResponseStatus`

審核 Google Form 的回應(`google_form_responses.status`):
- 0 → 待審核(預設,排程同步進來時的狀態)
- 1 → 通過
- 2 → 不通過

審核通過後,**通常會觸發 EventRelation.status 同步更新**(待補的業務規則)。

---

## 4. 系統路由

| Method | Path | 說明 |
|---|---|---|
| GET | `/up` | Laravel 健康檢查(`bootstrap/app.php` 設定) |
| GET | `/docs/api` | Scramble Swagger UI |
| GET | `/docs/api.json` | OpenAPI JSON |
| GET | `/telescope` | Laravel Telescope 監控面板(僅 dev) |

---

## 5. 速率限制 / Rate Limiting

| 端點 | 機制 | 設定 |
|---|---|---|
| 全部 | **目前無** | Roadmap:加 Laravel `RateLimiter` 或 nginx `limit_req` |
| `/api/edm/mail/inviteMail` | **強烈建議加上**(避免誤觸發大量寄信) | TBD |

---

## 6. CORS

由 `EDM_FRONTEND_URL` 環境變數控制,預設僅允許設定的 EDM 前端 origin。

```
EDM_FRONTEND_URL=https://uatedm.hwacom.com
```

設定來源:[`config/sso.php`](../config/sso.php)。

---

## 7. 錯誤處理

| 情境 | 表現 |
|---|---|
| Validation 失敗 | Laravel 預設 422 + JSON 列出每個欄位錯誤 |
| JWT 無效 | `AuthorizeJwt` 回 `{"message": "Unauthorized: ...", "error_type": "..."}` (HTTP 401) |
| IP 不在白名單 | `{"message": "IP not allowed"}` (HTTP 403) |
| 找不到資源 | Repository 用 `firstOrFail()`,Laravel 回 404 |
| 未捕捉例外 | dev: 顯示 stack trace;prod: `{"message": "Server Error"}` (HTTP 500) |

> 所有例外都會被 Laravel Telescope 紀錄,可在 `/telescope/exceptions` 查看(dev only)。

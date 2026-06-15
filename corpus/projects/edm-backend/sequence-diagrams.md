# Sequence Diagrams

本文件用 UML Sequence Diagram 描述 EDM Backend 的關鍵互動流程。目標讀者:**SA、開發者、想理解跨系統時序的 Reviewer**。

涵蓋三個流程:

1. JWT 驗證 — 收到請求到通過 middleware 的時序
2. 寄送活動邀請信 — 從 controller 到 AWS SES 的非同步流程
3. Google Form 回應同步 — 排程 cron 拉資料的流程

---

## 1. JWT 驗證流程

「前端帶 JWT 來,EDM Backend 怎麼確認這個 token 是真的、是誰?」

```mermaid
sequenceDiagram
    autonumber
    actor user as 行銷人員 (Browser)
    participant fe as EDM Frontend<br/>(Vue/Vben)
    participant nginx as edm-nginx
    participant app as Laravel App<br/>(php-fpm)
    participant mw as AuthorizeJwt<br/>Middleware
    participant ctrl as Controller<br/>(e.g. EventController)
    participant svc as Service / Repository

    Note over user,fe: 假設使用者已透過中台拿到 JWT,存在 localStorage
    user->>fe: 點「活動列表」
    fe->>nginx: POST /api/edm/event/list<br/>Authorization: Bearer <jwt>
    nginx->>app: fastcgi_pass app:9000<br/>(同 request)

    app->>mw: 進入 AuthorizeJwt::handle()
    mw->>mw: 1. 檢查 Authorization header 格式
    alt header 缺失或非 Bearer
        mw-->>fe: HTTP 401<br/>{"message":"Authorization Token not found"}
    end

    mw->>mw: 2. 取出 token,讀取 config('app.key')
    Note right of mw: 若 APP_KEY 是 base64:xxx 格式,先 base64_decode

    mw->>mw: 3. JWT::decode(token, new Key(APP_KEY, 'HS256'))
    Note right of mw: 用 firebase/php-jwt 套件本地驗證,<br/>不打中台

    alt 簽章正確且未過期
        mw->>mw: 4. $request->merge(['auth' => (array)$decoded])
        mw->>ctrl: $next($request)
        ctrl->>svc: 呼叫業務邏輯
        svc-->>ctrl: result
        ctrl-->>fe: HTTP 200<br/>{"code":0,"data":{...}}
    else 簽章錯 / 過期 / 結構壞
        mw->>mw: Log::error(失敗原因)
        mw-->>fe: HTTP 401<br/>{"message":"Unauthorized: <reason>",<br/>"error_type":"<ExceptionClass>"}
    end
```

**關鍵設計**

| 步驟 | 設計考量 |
|---|---|
| 3 — 本地驗證 | 不打中台 → 中台短暫不可用,EDM Backend 仍能服務已登入使用者 |
| 4 — `auth` 注入 request | Controller 可以 `$request->input('auth.email')` 取使用者身分,不需要再解一次 token |
| 失敗 log | 帶 `token_sample`(前 15 字)與 `secret_length`,協助偵測「key 不對齊」這種典型部署錯誤 |

**對比中台的 verify 方式**(若改走中台 verify):

| 方式 | 優點 | 缺點 |
|---|---|---|
| **本地驗 (現選)** | 中台離線不影響、效能好、無網路成本 | 需共用 SECRET_KEY,洩漏風險集中 |
| **回中台 verify** | EDM Backend 不持有 secret,中台可立即撤銷 | 中台變單點,每個 request 加 RTT |

詳見 [adr/0001-jwt-shared-secret.md](./adr/0001-jwt-shared-secret.md) 的取捨討論。

---

## 2. 寄送活動邀請信

「行銷人員按下『寄邀請』,系統如何把信送出去?」

```mermaid
sequenceDiagram
    autonumber
    actor user as 行銷人員
    participant fe as EDM Frontend
    participant ctrl as MailController
    participant er_repo as EventRelationRepository
    participant queue as DB Queue<br/>(jobs table)
    participant worker as Queue Worker<br/>(php artisan queue:work)
    participant job as SendAwsMailJob
    participant ses_svc as AwsSesService
    participant ses as AWS SES

    user->>fe: 按「寄邀請」按鈕
    fe->>ctrl: POST /api/edm/mail/inviteMail<br/>{event_id, subject, body_template, from}

    ctrl->>er_repo: getInviteList(event_id)
    er_repo-->>ctrl: List<EventRelation> (含 email_id snapshot)

    ctrl->>ctrl: 解析 body_template(替換 {name} 等變數)
    ctrl->>ctrl: 把 List 切成 chunk (預設 100/chunk)

    loop 每個 chunk
        ctrl->>queue: dispatch(new SendAwsMailJob($chunk))
        Note right of queue: INSERT INTO jobs<br/>(payload = serialized $chunk)
    end

    ctrl-->>fe: HTTP 200<br/>{"code":0,"data":{"queued":187,"chunks":2}}
    Note over fe,ctrl: 同步 API 即時回應,<br/>實際寄送非同步進行

    Note over worker: --- 以下發生在 background ---

    worker->>queue: SELECT ... FROM jobs<br/>WHERE reserved_at IS NULL
    queue-->>worker: Job payload
    worker->>job: handle()

    loop 每筆 mail
        job->>ses_svc: sendMail(email, subject, body, from)
        ses_svc->>ses: AWS SDK SendEmail API
        alt 成功
            ses-->>ses_svc: MessageId
            ses_svc-->>job: ok
        else 失敗 (rate limit / hard bounce)
            ses-->>ses_svc: Exception
            ses_svc-->>job: throw
        end
    end

    alt Job 全部成功
        job->>queue: DELETE FROM jobs WHERE id=...
    else Job throw
        job->>queue: 重試 (Laravel 預設 3 次)
        Note right of queue: 三次都失敗 → 進 failed_jobs 表
    end
```

**設計重點**

- **同步 API 立即回 200**:User 不用等寄信完成,UX 即時
- **Chunk 100 筆**:平衡 SES API rate limit 與 Job 顆粒度(太大難重試,太小 queue 開銷大)
- **Email_id snapshot**:寄信用的 email 從 `event_relation.email_id` 取,**不是即時查 member 的 primary email**(因為邀請當下凍結了)
- **失敗進 `failed_jobs`**:可手動 `php artisan queue:retry all` 補寄

**Roadmap**

- 加 webhook 接 SES 的 bounce / complaint event,自動更新 `event_relation.status`
- 加 `inviteMail` rate limit,避免誤觸發大量寄信(對應 [api-spec.md 第 5 節](./api-spec.md#5-速率限制--rate-limiting))

---

## 3. Google Form 回應同步

「使用者填了 Google Form,系統怎麼把回應拉進 DB?」

```mermaid
sequenceDiagram
    autonumber
    actor scheduler as Laravel Scheduler<br/>(每小時觸發)
    participant cmd as SyncGoogleForms<br/>Console Command
    participant gf_repo as GoogleFormRepository
    participant gapi_svc as GoogleApiService
    participant google as Google Forms API
    participant resp_repo as GoogleFormResponseRepository
    participant stat_repo as GoogleFormStatRepository

    scheduler->>cmd: php artisan app:sync-google-forms
    cmd->>gf_repo: 取得所有未軟刪的 google_form
    gf_repo-->>cmd: List<GoogleForm>

    loop 每個 form
        cmd->>gapi_svc: listResponses(form_id)
        gapi_svc->>google: GET forms/{form_id}/responses
        google-->>gapi_svc: { responses: [...], totalCount }
        gapi_svc-->>cmd: 回應陣列

        loop 每筆 response
            cmd->>resp_repo: upsert(google_response_id, ...)
            Note right of resp_repo: ON CONFLICT(google_response_id)<br/>不重複寫入
        end

        cmd->>gapi_svc: getViewCount(form_id)
        gapi_svc->>google: (Forms API 取 view metric)
        google-->>gapi_svc: view_count
        gapi_svc-->>cmd: view_count

        cmd->>stat_repo: updateOrCreate(<br/>  event_id, google_form_id,<br/>  view_count, response_count<br/>)
    end

    cmd-->>scheduler: exit 0
```

**關鍵設計**

| 步驟 | 設計考量 |
|---|---|
| `google_response_id` 唯一索引 | 排程跑多次也不會重複寫入(冪等) |
| 排程 = hourly | 行銷活動報名不需要即時,1 hr 延遲可接受;避免 Google API 配額耗盡 |
| `status` 預設 0 (待審核) | 自動同步進來不直接列入名單,需行銷人員審核 |

**對應排程設定**(在 [`routes/console.php`](../routes/console.php)):

```php
Schedule::command('app:sync-google-forms')->hourly();
```

要在 host 啟動 scheduler:

```bash
docker exec edm-backend-app php artisan schedule:work
```

> 實際 production 通常用 cron + `php artisan schedule:run` 每分鐘執行。詳見 [`deployment.md`](./deployment.md) 的 Background services 章節。

---

## 4. 跨系統一覽(對應中台)

EDM Backend 與其他系統的所有互動點,整合 view:

```mermaid
sequenceDiagram
    actor user as End User
    participant fe as EDM-FE
    participant mp as Middle Platform
    participant be as EDM-BE
    participant ses as AWS SES
    participant google as Google API

    Note over user,google: --- 登入流程(由中台主導)---
    user->>fe: 進站
    fe->>mp: 沒登入 → redirect /sso/login
    Note right of mp: Magic Link 流程,<br/>詳見中台 user-flow.md
    mp-->>fe: redirect ?token=<jwt>

    Note over user,google: --- 業務操作(EDM-BE 主場)---
    fe->>be: POST /api/edm/* + Bearer JWT
    be->>be: 本地驗 JWT (HS256, APP_KEY)
    be-->>fe: 業務資料

    Note over user,google: --- 寄信(非同步)---
    fe->>be: POST /api/edm/mail/inviteMail
    be-->>fe: HTTP 200 (queued)
    be->>ses: AWS SDK (background worker)

    Note over user,google: --- Google Form(背景)---
    Note right of be: hourly cron
    be->>google: GET forms/.../responses
    google-->>be: response data
```

完整的中台側流程見 [Middle Platform user-flow.md](../../Middle_Platform/docs/user-flow.md)。

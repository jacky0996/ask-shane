# Sequence Diagrams

本文件用 UML Sequence Diagram 描述 Job Digger Admin 的關鍵互動流程。目標讀者:**SA、開發者、想理解跨系統時序的 Reviewer**。

涵蓋以下流程:

1. SSO 進站(Web Mode)— 從沒登入到看見業務頁
2. Search Config CRUD(常見業務操作)
3. 使用者手動觸發爬蟲(今日 keyword)
4. 排程觸發爬蟲(非今日 keyword)

---

## 1. SSO 進站流程

「使用者第一次點 Admin URL,系統如何處理沒登入這件事?」

```mermaid
sequenceDiagram
    autonumber
    actor U as 使用者 (Browser)
    participant N as Nginx :8084
    participant A as Laravel App
    participant MW as AuthorizeJwtSso<br/>middleware
    participant DB as MariaDB<br/>(users 表)
    participant MP as Middle Platform :80

    Note over U: 第一次進站,沒 Laravel session
    U->>N: GET http://localhost:8084/
    N->>A: fastcgi_pass app:9000
    A->>MW: Pipeline 進入 middleware

    MW->>MW: Auth::check() → false
    MW->>MW: ?token= → 無
    MW->>MW: session['url.intended'] = '/'
    MW-->>U: 302 → http://localhost/sso/login/?redirect=http://localhost:8084/sso/callback

    U->>MP: GET /sso/login/?redirect=...
    Note over MP: Magic Link 流程<br/>(詳見中台 user-flow.md)
    MP-->>U: 302 → http://localhost:8084/sso/callback?token=<JWT>

    U->>N: GET /sso/callback?token=<JWT>
    N->>A: fastcgi_pass
    A->>MW: middleware 攔截

    MW->>MW: Auth::check() → false
    MW->>MW: $request->query('token') → <JWT>
    MW->>MW: decodeJwt(token) using SSO_JWT_SECRET (HS256)

    alt JWT valid
        MW->>DB: User::firstOrCreate(['email' => $payload->email], [...])
        DB-->>MW: User instance
        MW->>MW: Auth::login($user, true)
        MW->>MW: session()->regenerate()
        MW-->>U: 302 → redirect()->intended('/')
        U->>N: GET /
        N->>A: fastcgi_pass
        A->>MW: middleware
        MW->>MW: Auth::check() → true ✓
        MW->>A: next() → 業務 controller
        A-->>U: 渲染業務頁(redirect 到 /search-configs)
    else JWT invalid (過期 / 簽章錯)
        MW->>MW: Log::warning(失敗原因)
        MW-->>U: 302 → 中台 /sso/login/(重來)
    end
```

**關鍵設計細節**

| 步驟 | 為什麼這樣做 |
|---|---|
| `redirect URL = APP_URL/sso/callback`(固定) | 中台白名單比較容易管,且永遠回到固定接點 |
| `session['url.intended']` | Laravel 內建機制,登入完後 `intended('/')` 自動跳回 |
| `firstOrCreate by email` | email 是中台真實識別,本地 user 只是 mirror |
| `Auth::login + session::regenerate` | 防 session fixation attack |

詳細的 middleware code 見 [`app/Http/Middleware/AuthorizeJwtSso.php`](../app/Http/Middleware/AuthorizeJwtSso.php)。

---

## 2. Search Config CRUD 流程

「我登入後新增一個關鍵字,發生什麼?」

```mermaid
sequenceDiagram
    autonumber
    actor U as 行銷人員
    participant V as Blade view<br/>(search_configs/create)
    participant C as SearchConfigController
    participant M as SearchConfig Model
    participant DB as MariaDB<br/>(search_configs 表)

    U->>V: 進「關鍵字 → 新增」頁
    V-->>U: 渲染表單

    U->>C: POST /search-configs<br/>{keyword: "PHP", title_tags: "php,後端", content_tags: "php,後端"}
    C->>C: middleware (AuthorizeJwtSso) 通過 ✓
    C->>C: validate (keyword required, unique)

    alt validation 通過
        C->>M: SearchConfig::create(...)
        M->>DB: INSERT INTO search_configs (keyword, title_tags, content_tags, created_at) VALUES (?, ?, NOW())
        DB-->>M: id
        M-->>C: SearchConfig instance
        C-->>U: 302 → /search-configs (列表頁)
        Note over U: with success flash message
    else validation 失敗(例如 keyword 重複)
        C-->>U: 302 → 上一頁 + errors
    end
```

**重點**:
- middleware 只在 **request 進來時驗一次**,過了之後 controller 用 `Auth::user()` 取目前 user 不必再驗 JWT
- `unique:search_configs,keyword` 在 FormRequest validation 已經擋了重複,DB 的 UNIQUE INDEX 是 last line of defense

---

## 3. 使用者手動觸發爬蟲(今日 keyword)

「使用者剛建好 keyword 想立刻看結果,系統如何串到 job-digger?」

> 設計約束:**只有今日建立的 keyword** 才會在 admin 看到「更新」按鈕,過往 keyword 由排程處理(見第 4 節)。

```mermaid
sequenceDiagram
    autonumber
    actor U as 使用者 (Browser)
    participant V as 關鍵字列表頁 (Blade)
    participant API as job-digger FastAPI :85
    participant DB as MariaDB<br/>(vacancies / search_configs)

    Note over V: Blade 渲染時用 $config->isCreatedToday()<br/>決定是否顯示「更新」按鈕

    U->>V: 點「更新」(綠色按鈕)
    V->>U: confirm("⚠️ 資料 ETL 提醒,預計 30~60 分鐘...")
    U->>V: 確定

    V->>API: fetch POST http://localhost:85/api/scrape/{id}
    API->>DB: 守衛:SELECT created_at = today AND id = ?

    alt 非今日(403)
        API-->>V: HTTP 403 "此關鍵字非今日建立..."
    else 同 keyword 在跑(400)
        API-->>V: HTTP 400 "此關鍵字的抓取任務已在執行中"
    else 別的 keyword 在跑(409 全域鎖)
        API-->>V: HTTP 409 "另一個關鍵字正在執行中"
    else 通過所有檢查
        API->>API: BackgroundTasks.add_task(start_scraping_task)
        API-->>V: HTTP 200 {"status": "accepted"}
        V-->>U: alert "✅ 已開始,任務在背景執行"
    end

    Note over API: --- 背景非同步進行 ---
    API->>API: Stage A: 抓清單
    API->>API: Stage B: 內文清洗(僅 check_type=NULL or 偵測逾時)
    API->>API: Stage C: 公司資訊補全(僅資本額/員工數空的)
    API->>DB: UPSERT vacancies + UPDATE search_configs.last_scraped_at = NOW()

    Note over U: 使用者可去其他頁
    U->>V: 重整列表
    V->>DB: SELECT search_configs (Eloquent)
    V-->>U: 顯示「最後爬蟲」時間更新
```

**錯誤碼總表**

| HTTP | 場景 | 前端訊息 |
|---|---|---|
| 200 | 啟動成功 | ✅ 已開始,任務在背景執行 |
| 400 | 同 keyword 已在跑 | ⏸ 此關鍵字的任務已在執行中 |
| 403 | 非今日建立(守衛) | ⛔ 此關鍵字非今日建立,將由排程自動執行 |
| 404 | config_id 不存在 | ❌ 啟動失敗 |
| 409 | 別的 keyword 在跑(全域鎖) | ⏸ 另一個關鍵字正在執行中,請稍後再試 |

---

## 4. 排程觸發爬蟲

「過往 keyword 怎麼定期更新?排程是怎麼跑的?」

```mermaid
sequenceDiagram
    autonumber
    participant SUP as supervisord (PID 1)
    participant SW as schedule:work<br/>(php artisan)
    participant CMD as ScrapeAllPending<br/>command
    participant DB as MariaDB
    participant API as job-digger FastAPI :85

    Note over SUP: container 啟動時 entrypoint exec /usr/bin/supervisord
    SUP->>SW: 子程序 1:php-fpm (web)
    SUP->>SW: 子程序 2:php artisan schedule:work

    Note over SW: schedule:work 每分鐘自動 schedule:run
    loop 每分鐘
        SW->>SW: schedule:run (檢查時間表)
    end

    Note over SW: 03:00 觸發 scrape:all-pending
    SW->>CMD: php artisan scrape:all-pending
    CMD->>DB: SELECT * FROM search_configs<br/>WHERE created_at != today<br/>ORDER BY last_scraped_at NULLS FIRST, ASC

    loop 每個 pending keyword (序列)
        CMD->>API: POST /api/scrape/{id}

        alt 200 接受
            CMD-->>CMD: 進入輪詢
            loop 每 30 秒 (poll_interval)
                CMD->>API: GET /api/scrape/status/{id}
                API-->>CMD: {"is_running": ?, "stage": ?}
                Note over CMD: 直到 is_running=false<br/>或超過 task_timeout(預設 2hr)
            end
        else 409 全域鎖
            CMD->>CMD: skip,留給下次 schedule
        else 403 / 其他
            CMD->>CMD: log warning,跳下一個
        end
    end

    CMD-->>SW: 結束(成功 / 失敗 / 略過 計數)
    SW->>SW: appendOutputTo(storage/logs/scrape-all-pending.log)
```

**設計重點**

| 項 | 說明 |
|---|---|
| 為何序列化 | job-digger 全域只允許一個 keyword 同時跑(避免多隻 Chromium 爆 RAM、CF ban) |
| 為何排除今日 | 使用者通常剛建好就想看結果,不想等到隔天;排程跳過今日避免和手動觸發撞車 |
| 為何用 schedule:work | Laravel 11 內建,自帶分鐘 ticker,**取代傳統 cron**;supervisor 管 long-running 重啟邏輯一致 |
| `withoutOverlapping(120)` | 跨日還沒跑完就不重複觸發(整輪 1~2 小時,鎖 120 分鐘安全) |
| `task_timeout` | 單筆 keyword 超過 2 小時視為卡死,放棄等待繼續下一個 |
| 觀測 | `storage/logs/scrape-all-pending.log` + `docker logs job_digger_admin_app`(supervisor stdout passthrough) |

**手動測試命令**

```bash
# 看會處理哪些 keyword(不實際觸發)
docker exec -it job_digger_admin_app php artisan scrape:all-pending --dry-run

# 實際跑(忽略 03:00 排程,立刻執行)
docker exec -it job_digger_admin_app php artisan scrape:all-pending

# 確認 supervisor 兩支程序都活著
docker exec job_digger_admin_app supervisorctl status

# 看排程列表
docker exec job_digger_admin_app php artisan schedule:list
```
## 5. 登出流程

```mermaid
sequenceDiagram
    actor U as 使用者
    participant A as Laravel App
    participant MP as 中台

    U->>A: GET /sso/logout
    A->>A: SsoController::logout()
    A->>A: Auth::logout()
    A->>A: session::invalidate() + regenerateToken()
    A-->>U: 302 → http://localhost/sso/logout/

    U->>MP: GET /sso/logout/
    MP->>MP: 清中台 session
    MP-->>U: 302 → /sso/login/(回到中台登入頁)
```

**注意**:中台 logout 不會撤銷已簽出去的 JWT(JWT 是無狀態的)。在 Admin 端的 `Auth::logout` 只清本地 session,但 30 分鐘內如果有人複製了 token 還能再進來(走 SSO callback 路徑驗 JWT 通過後重建 session)。要立即撤銷需要 token blacklist,目前 SSO 流程未實作。

---

## 6. 跨系統 overview

整合三個流程的整體 view:

```mermaid
sequenceDiagram
    actor U as 使用者
    participant A as Admin
    participant MP as Middle Platform
    participant JD as job-digger
    participant DB as 共用 MariaDB

    Note over U,DB: --- 第一次登入 ---
    U->>A: 進站
    A-->>U: redirect 中台
    U->>MP: Magic Link 登入
    MP-->>U: redirect 回 Admin /sso/callback?token=...
    U->>A: callback
    A->>DB: User::firstOrCreate
    A-->>U: 進業務頁

    Note over U,DB: --- 業務操作 ---
    U->>A: 設關鍵字
    A->>DB: INSERT search_configs
    U->>A: 看職缺
    A->>DB: SELECT vacancies

    Note over U,DB: --- 手動觸發爬蟲(今日 keyword) ---
    U->>A: 點「更新」
    A->>JD: POST /api/scrape/{id}
    JD->>JD: background task: list/content/company
    JD->>DB: UPSERT vacancies
```

完整中台側的 SSO 細節見 [Middle Platform user-flow.md](../../Middle_Platform/docs/user-flow.md)。
完整 job-digger 側的爬蟲細節見 [job-digger sequence-diagrams.md](../../job-digger/docs/sequence-diagrams.md)。

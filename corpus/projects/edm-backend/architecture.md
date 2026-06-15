# Architecture

本文件描述 EDM Backend 的程式分層、模組組成、與外部整合介面。採 C4 Model 的 Container / Component 兩層 + Class Diagram。

目標讀者:**開發者、Architect、想理解內部結構的 Reviewer**。

---

## Level 1 — System Context

「這個系統服務誰、又依賴誰?」見 [`overview.md` 第 2 節](./overview.md#2-在生態裡的位置)。

---

## Level 2 — Container Diagram

「把系統打開來看,裡面有哪些獨立部署單元?」

```mermaid
flowchart TB
    fe["📦 EDM Frontend<br/>(Vue / Vben SPA)<br/>:82"]

    subgraph compose["docker-compose (3 services, backend bridge network)"]
        direction TB

        nginx["📦 edm-nginx<br/>nginx:alpine<br/>:81 → :80<br/>fastcgi_pass app:9000"]

        subgraph app_box["📦 edm-backend-app"]
            app_fpm["php:8.2-fpm<br/>:9000"]
            app_queue["queue:worker<br/>(若另開)"]
            app_sched["scheduler<br/>(SyncGoogleForms hourly)"]
        end

        db[("🗄 edm-db<br/>mysql:8.4<br/>host :3307 → :3306<br/>volume: dbdata")]

        nginx --> app_fpm
        app_fpm --> db
        app_queue --> db
        app_sched --> db
    end

    mp["🔐 Middle Platform<br/>(SSO IdP)<br/>共享 APP_KEY"]
    ses["✉ AWS SES"]
    google["📋 Google APIs<br/>Forms / Sheets / Drive"]

    fe -- "POST /api/edm/*<br/>Bearer JWT" --> nginx
    fe -. "(redirect 取得 JWT)" .-> mp
    app_fpm -- "本地驗 JWT (HS256, APP_KEY)" --> app_fpm
    app_queue -- "send mail" --> ses
    app_sched -- "sync responses" --> google
```

**容器清單**

| 容器 | 角色 | Host Port | Container Port |
|---|---|---|---|
| `edm-nginx` | 反向代理、TLS 終止點 | **81** | 80 |
| `edm-backend-app` | Laravel App (PHP-FPM) | — | 9000 |
| `edm-db` | MySQL 8.4 | **3307**(僅本機 DB IDE 用) | 3306 |

> **Port 設計**:Laravel 容器內透過 `db:3306` 連 DB(同網段),host 上 `3307` 純粹避免跟 host 既有的 3306 撞。詳見 [`deployment.md`](./deployment.md)。

---

## Level 3 — Component Diagram(Laravel App 內部分層)

「app 容器裡面,程式碼是怎麼分層的?」

```mermaid
flowchart TB
    subgraph routes["routes/Api/edm.php"]
        r["所有 /api/edm/* 路由<br/>(Member / Group / Event / Mail)"]
    end

    subgraph mw["Middleware"]
        jwt["AuthorizeJwt<br/>(Firebase JWT, HS256)"]
        ip["WhitelistIpMiddleware<br/>(sso.allowed_edm_ips)"]
    end

    subgraph http["HTTP Layer (app/Http/Controllers/EDM/)"]
        member_c["MemberController"]
        group_c["GroupController"]
        event_c["EventController"]
        mail_c["MailController"]
    end

    subgraph svc["Service Layer (app/Services/)"]
        user_s["UserService"]
        ses_s["AwsSesService<br/>(AWS SDK)"]
        gf_s["GoogleFormService"]
        gapi_s["GoogleApiService<br/>(google/apiclient)"]
    end

    subgraph repo["Repository Layer (app/Repositories/)"]
        edm_r["EDM/*Repository"]
        google_r["Google/*Repository"]
        base_r["Repository (base)<br/>+ RepositoryTrait"]
    end

    subgraph domain["Domain (app/Models/)"]
        edm_m["EDM/* Models<br/>(Member, Group, Event, ...)"]
        google_m["Google/* Models<br/>(GoogleForm, Response, Stat)"]
    end

    subgraph jobs["Jobs (app/Jobs/Common/)"]
        send_mail["SendAwsMailJob"]
    end

    subgraph console["Console Commands"]
        sync["SyncGoogleForms<br/>(hourly cron)"]
    end

    subgraph present["app/Presenters/"]
        prst["輸出格式化"]
    end

    r --> mw
    mw --> http

    http --> svc
    http --> repo
    http --> jobs

    svc --> repo
    svc --> ses_s
    svc --> gapi_s

    repo --> base_r
    repo --> domain

    jobs --> ses_s
    jobs --> repo

    sync --> gf_s
    sync --> google_r

    http -.-> present
    present -.-> domain
```

**分層職責**

| 層 | 資料夾 | 該做什麼 | 不該做什麼 |
|---|---|---|---|
| **Routes** | `routes/Api/edm.php` | 對映 path → controller method | 任何商業邏輯 |
| **Middleware** | `app/Http/Middleware/` | 橫切關注點(JWT 驗證、IP 白名單) | 商業邏輯、DB 寫入 |
| **Controllers** | `app/Http/Controllers/EDM/` | 接 request → 呼叫 service / repo → 回 response | 直接寫 SQL、跨 service 編排業務 |
| **Services** | `app/Services/` | 跨 entity 的業務邏輯、外部 API 呼叫(SES、Google) | 封裝單表 CRUD |
| **Repositories** | `app/Repositories/` | 單表 CRUD + 複雜查詢 | 業務規則(屬於 service) |
| **Models** | `app/Models/` | Eloquent + relations + casts + accessor | 跨 entity 的業務邏輯 |
| **Jobs** | `app/Jobs/Common/` | 重副作用、可重試的非同步任務 | 同步資料返回 |
| **Console Commands** | `app/Console/Commands/` | 排程任務(`Schedule::command()`) | HTTP 處理 |
| **Presenters** | `app/Presenters/` | 統一的輸出資料格式 | DB 操作 |

> **為何用 Repository Pattern?** Laravel 不強制 — 但本專案有「單元測試需要 mock data layer」與「同一張表常被多 controller 查」兩個需求,所以拉出 Repository 集中查詢邏輯。`Repository` 基底類別 + `RepositoryTrait` 提供共用方法(分頁、軟刪除過濾)。

---

## Level 4 — Class Diagram(核心 Domain Model 關聯)

「主要業務 entity 之間的關係」

```mermaid
classDiagram
    direction LR

    class Member {
        +bigint id
        +string name [10]
        +int status [0=未驗證, 1=正常]
        +string sales_email [nullable]
        +timestamps + softDeletes
        --
        +emails() : HasMany~Emails~
        +mobiles() : HasMany~Mobiles~
        +organization() : BelongsTo~Organization~
        +groups() : BelongsToMany~Group~
        +events() : BelongsToMany~Event~ via EventRelation
    }

    class Emails {
        +bigint id
        +bigint member_id [FK]
        +string email
        +bool is_primary
    }

    class Mobiles {
        +bigint id
        +bigint member_id [FK]
        +string mobile
    }

    class Organization {
        +bigint id
        +string name
        +HasMany~Member~
    }

    class Group {
        +bigint id
        +string name
        +int status
        --
        +members() : BelongsToMany~Member~
        +events() : BelongsToMany~Event~
    }

    class Event {
        +bigint id
        +string event_number "Bxxx 格式"
        +string title
        +text content
        +datetime start_time
        +datetime end_time
        +int type
        +int status
        +int is_approve [0|1]
        +int is_display [0|1]
        +int is_qrcode [0|1]
        +string creator_email
        +timestamps + softDeletes
        --
        +relations() : HasMany~EventRelation~
        +invitedMembers() : BelongsToMany~Member~ via EventRelation
        +googleForm() : HasOne~GoogleForm~
    }

    class EventRelation {
        +bigint id
        +bigint event_id [FK]
        +bigint member_id [FK]
        +int status "邀請/已寄/已回覆..."
    }

    class GoogleForm {
        +bigint id
        +bigint event_id [FK]
        +string form_id
        +string title
        --
        +event() : BelongsTo~Event~
        +responses() : HasMany~GoogleFormResponse~
        +stats() : HasOne~GoogleFormStat~
    }

    class GoogleFormResponse {
        +bigint id
        +bigint google_form_id [FK]
        +json answers
        +int status "稽核狀態"
    }

    class GoogleFormStat {
        +bigint id
        +bigint google_form_id [FK]
        +int total_responses
        +int approved_responses
    }

    Member "1" --o "0..*" Emails
    Member "1" --o "0..*" Mobiles
    Organization "1" --o "0..*" Member
    Group "1..*" --o "0..*" Member : (group_member 中介表)
    Event "1" --o "0..*" EventRelation
    Member "1" --o "0..*" EventRelation
    Event "1" --o "0..1" GoogleForm
    GoogleForm "1" --o "0..*" GoogleFormResponse
    GoogleForm "1" --o "0..1" GoogleFormStat
```

**設計重點**

- **Member 拆 Email / Mobile 為獨立表**:一個會員可有多組聯絡方式;寄信時 join `emails` 取主要 email
- **Group ↔ Member 用中介表**:Eloquent `BelongsToMany`,加入時間 / 加入者可記在 pivot
- **Event ↔ Member 透過 EventRelation**:不直接 ManyToMany,因為 EventRelation 自己有 `status` 等業務欄位(不只是關聯,本身是 entity)
- **GoogleForm 為 1:1 綁 Event**:每場活動最多一張表單;表單回應透過 cron 同步入庫,不即時拉
- **所有業務 entity 用 SoftDelete**:詳見 [adr/0003-soft-deletes.md](./adr/0003-soft-deletes.md)

> 對應 DB 視角的詳述請見 [`data-model.md`](./data-model.md)。

---

## Level 5 — State Diagram(關鍵 Entity 生命週期)

幾個有 `status` 欄位的 entity 都有狀態機概念。最重要的兩個:

### 5.1 Member.status

```mermaid
stateDiagram-v2
    [*] --> 未驗證 : MemberController.add (status=0)
    未驗證 --> 正常 : editStatus (status=1)<br/>(經過業務確認)
    正常 --> 未驗證 : editStatus (status=0)<br/>(暫停發信)
    正常 --> [*] : softDelete (deleted_at set)
    未驗證 --> [*] : softDelete
```

### 5.2 GoogleFormResponse.status(回應審核流)

```mermaid
stateDiagram-v2
    [*] --> 待審核 : SyncGoogleForms 同步進來
    待審核 --> 通過 : updateResponseStatus
    待審核 --> 拒絕 : updateResponseStatus
    通過 --> [*] : (列入正式名單)
    拒絕 --> [*]
```

> Event 也有 `status` / `is_approve` / `is_display` / `is_qrcode` 四個狀態旗標,但設計上是「**獨立旗標而非單一狀態機**」(可同時 approve + display + qrcode),所以不畫 state machine。若未來合併成單一 enum,再補狀態圖。

---

## 6. 跨系統互動(摘要)

完整 sequence 見 [`sequence-diagrams.md`](./sequence-diagrams.md)。簡述:

| 互動場景 | 對手 | 介面 |
|---|---|---|
| 收到前端請求 | EDM Frontend | HTTPS POST `/api/edm/*` + Bearer JWT |
| 驗證 JWT | (本地) | `firebase/php-jwt` 用 `APP_KEY` 解碼 |
| 寄活動邀請信 | AWS SES | `AwsSesService` (AWS SDK) |
| 同步 Google Form 回應 | Google APIs | `GoogleApiService` + `GoogleFormService`,每小時 cron |
| 健康檢查 | Ops / LB | `GET /up`(Laravel 內建) |

---

## 7. Roadmap / 已知架構限制

| 項目 | 現況 | 下一步 |
|---|---|---|
| JWT middleware | 在 `routes/Api/edm.php` 被註解掉 | 正式環境必須開啟 |
| Queue Worker | 未在 compose 預設 | 加 `worker` service,用同 image,`command: php artisan queue:work` |
| 觀測性 | Telescope 適合 dev,不適合 prod | 加 Sentry / OpenTelemetry export 到 prod |
| 測試 | PHPUnit 框架在,需補 controller / repo 測試 | 對 Member / Event 主流程加 feature test |
| Cache | DB driver(預設) | 高負載時切 Redis |
| Auth 升級 | HS256 共享密鑰 | 待中台升 RS256 + JWKS,本系統改用公鑰驗(去除 secret 共享風險) |

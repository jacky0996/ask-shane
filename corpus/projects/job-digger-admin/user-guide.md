# User Guide

本文件寫給**第一次用 Job Digger Admin** 的使用者(我自己 / 內部行銷)看。不談 JWT、不談架構,只講你會看到什麼、應該按哪裡。

---

## 1. 這是什麼?

Job Digger Admin 是「**104 職缺爬蟲後台**」,讓你可以:

- **設定爬蟲關鍵字**(例如「PHP 後端」)+ 過濾標籤
- **檢視抓回的職缺**(列表 + 搜尋 + 分頁)
- 系統會根據你設的關鍵字定期自動爬 104,過濾後存進 DB

**你不需要記密碼** — 系統登入是透過中台 SSO,輸入 Email 收信點連結即可。

---

## 2. 第一次登入

### 2.1 進入系統

打開瀏覽器,輸入:

```
http://localhost:8084/      ← 本機開發
```

### 2.2 自動跳轉到中台登入

第一次進站,系統會自動把你帶到**中台登入頁**:

```
Job Digger Admin (你看不到內容)
      ↓
中台登入頁 ─── 輸入 Email
      ↓
信箱收到「Middle Platform 登入連結」信
      ↓
點信中的「登入」按鈕(連結 15 分鐘有效)
      ↓
返回 Admin 看到主畫面
```

> 若收不到信:
> - 檢查垃圾信夾
> - 在 dev 環境信件是印到中台 docker logs(不真的寄)— 跑這個指令撈:
>   ```bash
>   docker logs middle_platform_web 2>&1 | grep "/sso/magic/" | tail -1
>   ```

### 2.3 進入後看到的畫面

成功登入後預設會被導到 **關鍵字設定頁**(`/search-configs`):

- 頂部:你的姓名(顯示登入身分)
- 主區域:關鍵字列表(若無,顯示「請新增關鍵字」)

---

## 3. 關鍵字管理(SearchConfig)

### 3.1 看關鍵字列表

側邊選單 → **關鍵字管理**

你會看到:
- **Keyword**(104 搜尋字,例如 "PHP")
- **Filter Tags**(逗號分隔的過濾標籤,例如 "php,後端,軟體")
- **Created At**(建立時間)
- **動作**:編輯 / 刪除

### 3.2 新增關鍵字

列表頁右上角 → **新增關鍵字**

填寫:

| 欄位 | 說明 | 範例 |
|---|---|---|
| **Keyword**(必填) | 104 搜尋框會輸入的字 | `PHP 後端` |
| **Filter Tags**(必填) | 二次過濾用,**標題需包含其一**才會被收進 DB | `php,PHP,後端,軟體,資訊` |

> **過濾規則**:`title_tags` / `content_tags` 是 OR 邏輯。例如 `"php,後端"` 代表標題只要含 "php" 或 "後端" 就保留,兩者都沒有就丟掉。
> **不要設太寬**(全部關鍵字爬下來)也不要太窄(可能漏好職缺)— 我自己是設 5-7 個常見替代詞。

### 3.3 編輯 / 刪除

每筆右側有「編輯」「刪除」按鈕。

**注意**:
- **編輯**會立即生效 — 下次跑爬蟲就用新關鍵字
- **刪除**會永久移除 search_config(沒有 soft delete),但**已抓回的 vacancies 不受影響**(它們有自己的 `keyword` 欄位 snapshot)

### 3.4 執行爬蟲(更新)

每筆右側根據關鍵字「建立日期」決定操作:

| 情況 | 看到什麼 | 行為 |
|---|---|---|
| **今日剛建立的 keyword** | 綠色「**更新**」按鈕 | 點下去會跳 ETL 提示 → 確定 → 觸發 job-digger 爬蟲 |
| **過往 keyword** | 「**由排程執行**」灰底標籤 | **不能手動觸發**,每天 03:00 會由排程自動更新 |

#### 點「更新」會發生什麼

1. 跳出 confirm 視窗:「⚠️ 資料 ETL 提醒,預計 30~60 分鐘...」
2. 你按「確定」之後:
   - 系統呼叫 job-digger FastAPI(`http://localhost:85`)
   - 觸發背景爬蟲(三階段:list / content filter / company info)
   - 按鈕變成「啟動中...」並 disable
   - 收到 ✅ 提示:「已開始,任務在背景執行」
3. **不會立即看到結果** — 爬蟲跑完通常 30~60 分鐘
4. 你可以離開這頁去做別的,稍後重新整理列表頁可以看到「**最後爬蟲**」欄位的時間更新

#### 為什麼過往 keyword 不能手動觸發

- 一個 keyword 完整跑完約 30~60 分鐘,**讓你在前台等不切實際**
- job-digger 後端**全域只允許一個 keyword 同時跑**(避免多隻 Chromium 把 RAM 跟 CPU 吃光),所以排程會序列化處理
- 後端有守衛檢查 — 即使你想用 curl 繞過,API 會回 `HTTP 403`
- 排程每天 **03:00** 自動跑,優先處理「最久沒更新」的 keyword

#### 「最後爬蟲」欄位

列表的「**最後爬蟲**」顯示的是 **`last_scraped_at`** 欄位 — 上次成功完整跑完(A→B→C 三階段)的時間。如果失敗中斷不會更新這個時間,所以你看到的時間永遠代表「上次拿到完整資料是多久以前」。

---

## 4. 職缺檢視(Vacancy)

### 4.1 看職缺列表

側邊選單 → **職缺搜尋**

你會看到爬蟲抓回的所有職缺,**預設 20 筆/頁**。每筆顯示:

- **Title**(職缺標題)
- **Company**(公司名稱)+ 連到 104 公司頁的連結
- **Salary**(原始薪資文字)
- **Capital / Employee Count**(公司資本額 / 員工數,Stage C 補進來的)
- **Keyword**(對應的搜尋字,看是哪次爬蟲抓的)
- **Check Type**(過濾分類)
- **Job Link**(連到 104 職缺頁)
- **Created**(抓取時間)

### 4.2 過濾與搜尋

頁面頂部有 **Keyword 下拉選單**,選一個關鍵字就只看該關鍵字抓回的職缺。

> Roadmap:加更多過濾條件(資本額 > X、員工數區間、status 等)

### 4.3 注意事項

- **職缺是唯讀的** — Admin 不能在 UI 改職缺資料(那是 job-digger 的責任)
- **重複職缺不會出現兩次** — `job_link` 是 unique,job-digger 用 UPSERT
- **職缺可能變舊** — 排程每天 03:00 自動更新所有非今日 keyword;當天剛建的 keyword 你也可以從關鍵字列表頁手動點「更新」

---

## 5. 系統內查文件

側邊選單 → **/help**(若有)

或直接看本目錄的 GitHub 渲染版本:

- [overview.md](./overview.md) — 為什麼有這個系統
- [architecture.md](./architecture.md) — 架構
- [adr/](./adr/) — 重大決策

---

## 6. 常見問題

### Q1: 我登入後過一陣子又被踢出去要重登?

A: 系統 Session **預設 120 分鐘**(由 `SESSION_LIFETIME` 控制)。120 分鐘內沒操作會自動登出,要重新走 SSO。如果你想長一點,改 `.env` 的 `SESSION_LIFETIME=480`(8 小時)再 restart。

### Q2: 我手滑刪錯一個關鍵字,救得回來嗎?

A: **目前救不回來** — 關鍵字沒做 soft delete(因為一般不會誤刪),只能重新建一次。但**已抓回的 vacancies 不受影響**(它們有 keyword snapshot)。

### Q3: 我可以同時開兩個分頁操作嗎?

A: **可以**,Laravel session 會共享。但避免兩個分頁同時編輯**同一筆**關鍵字。

### Q4: 為什麼有些 vacancies 的 Capital / Employee Count 是空的?

A: 那些是**剛抓回但還沒跑 Stage C(公司資料補完)**。下次 job-digger 跑爬蟲時 Stage C 會補進去。

### Q5: 為什麼我登入時跳到一個叫「Middle Platform」的網頁?

A: 那是**集中式登入服務**(SSO)。Middle Platform / EDM / Job Digger Admin 共用同一個登入,你只要登一次就能進所有系統。詳見中台的 [overview.md](../../Middle_Platform/docs/overview.md)。

### Q6: 我看不到「更新」按鈕?

A: 因為這個 keyword **不是今日建立的**。系統規則是:
- **今日建立** → 看到綠色「更新」按鈕,可以手動觸發
- **過往 keyword** → 顯示「由排程執行」,每天 03:00 自動跑

如果非要立刻跑某個過往 keyword,有兩種方式(僅限維運自己用,不是日常操作):
1. 在 admin 容器手動執行:`docker exec -it job_digger_admin_app php artisan scrape:all-pending` 一次跑掉所有 pending
2. 直接 curl 後端 API(會被 403 守衛擋下,要先把那筆 `created_at` 改成 today)

### Q7: 排程跑到一半我能停止嗎?

A: 重啟 admin 容器即可:`docker compose restart app`。supervisor 會把 `schedule:work` 跟 ScrapeAllPending 一起停掉。但要注意:**已經發出去給 job-digger 的那筆爬蟲**會繼續在 job-digger 那邊跑完,因為那是 background task,跟 admin 端解耦。要真的停 job-digger 端的話要 `docker compose -f /path/to/job-digger/docker-compose.yml restart`。

---

## 7. 進階:維運常用命令

### 7.1 看排程狀態

```bash
# 確認 supervisor 兩支 process 都活著
docker exec job_digger_admin_app supervisorctl status
# 預期:
#   php-fpm    RUNNING   pid 12, uptime ...
#   schedule   RUNNING   pid 13, uptime ...

# 看排程清單(Laravel 11)
docker exec job_digger_admin_app php artisan schedule:list

# 看排程 log(scrape:all-pending 每次跑都會 append)
docker exec job_digger_admin_app tail -f storage/logs/scrape-all-pending.log
```

### 7.2 立刻跑一輪排程(不等到 03:00)

```bash
# Dry-run:只列出會被處理的 keyword,不實際觸發
docker exec -it job_digger_admin_app php artisan scrape:all-pending --dry-run

# 實際跑(會逐一觸發 + 輪詢,可能跑很久)
docker exec -it job_digger_admin_app php artisan scrape:all-pending
```

### 7.3 直接打 job-digger API(繞過 admin)

```bash
# 看清單
docker exec job_digger_admin_app php artisan tinker --execute="
  echo App\Models\SearchConfig::all()->map(fn(\$c) => \$c->id . ': ' . \$c->keyword)->implode(\"\n\");
"

# 啟動 id=1 的爬蟲
curl -X POST http://localhost:85/api/scrape/1

# 看狀態
curl http://localhost:85/api/scrape/status/1

# 看 job-digger log
docker logs -f job_digger_api
```

注意:`POST /api/scrape/{id}` 有 today-only 守衛,只允許「今日建立」的 keyword 通過。

---

## 8. 聯絡誰?

| 問題 | 找誰 |
|---|---|
| 登入收不到信 | 看中台 docker logs(自己) |
| 系統 bug / 想加新功能 | 自己 fork 改 |
| 爬蟲爬不到 / 爬錯 | 看 job-digger docker logs |

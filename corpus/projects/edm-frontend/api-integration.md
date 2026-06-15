# API Integration

本文件描述 EDM Frontend 作為 **Client** 跟外部系統(中台 / EDM Backend / Google)整合的契約。

跟中台 / EDM Backend 的 `api-spec.md` 不同 — 那兩份是「我提供什麼 API」,本文件是「我消費哪些 API,怎麼包裝、怎麼處理錯誤」。

目標讀者:**前端開發者、SA、要新加 API 整合的人**。

---

## 1. 整合對象一覽

| 對象 | 流量出口 | 認證方式 | 對應契約文件 |
| --- | --- | --- | --- |
| **中台 (Middle Platform)** | nginx `/api-sso/*` (隱身代理) | 無(僅 token 交換) | [Middle Platform api-spec.md](../../Middle_Platform/docs/api-spec.md) |
| **EDM Backend (Laravel)** | nginx `/api/edm/*` | `Authorization: Bearer <jwt>` + `X-User-Info` | [edm_backend api-spec.md](../../edm_backend/docs/api-spec.md) |
| **Google Forms** | (不直接呼叫) | — | 由 EDM Backend 代理,前端透過 `/api/edm/event/*googleForm*` 操作 |
| **AWS SES** | (不直接呼叫) | — | 由 EDM Backend 代理,前端透過 `/api/edm/mail/inviteMail` 觸發 |

> **關鍵設計**:前端**永遠不直接打第三方**。所有外部 API key、所有跨域問題都由 nginx + 後端解決。

---

## 2. 統一的 API Client(`requestClient`)

封裝在 [`apps/web-ele/src/api/`](../apps/web-ele/src/api/),基於 Axios:

```ts
// 使用範例
import { requestClient } from '#/api/request';

const result = await requestClient.post('/api/edm/event/list', {
  page: 1,
  per_page: 20,
});
// result = { items: [...], total: 123, page: 1, per_page: 20 }
```

**設計重點**

- **回 `data` 而非整個 axios response** — 攔截器解開 `{code, data, message}`,業務 code 只拿 data
- **`code !== 0` 自動 throw** — 業務錯誤跟網路錯誤都用同一套 try-catch
- **不 expose URL** — 所有 endpoint 集中在 `apps/web-ele/src/api/<module>/<method>.ts`,業務 code 不直接寫 URL 字串

---

## 3. 攔截器設計

### 3.1 Request 攔截器

```ts
// 簡化示意
requestClient.interceptors.request.use((config) => {
  const authStore = useAuthStore();
  const userStore = useUserStore();

  // 1. 加 Authorization header
  if (authStore.accessToken) {
    config.headers.Authorization = `Bearer ${authStore.accessToken}`;
  }

  // 2. 加 X-User-Info header (Base64 編碼)
  if (userStore.userInfo) {
    config.headers['X-User-Info'] = btoa(
      unescape(encodeURIComponent(JSON.stringify(userStore.userInfo))),
    );
  }

  return config;
});
```

| Header | 來源 | 用途 |
| --- | --- | --- |
| `Authorization` | `useAuthStore().accessToken` | 標準 JWT,後端驗 |
| `X-User-Info` | `useUserStore().userInfo` (Base64) | 後端取使用者 metadata,**不需自己 decode JWT** |

> **為何 Base64 編碼 user info**:HTTP header 規範不允許 non-ASCII,`display_name` 含中文時會直接被 nginx / php 當成 invalid header 退回。Base64 化解這個問題。詳見 [adr/0003-x-user-info-header.md](./adr/0003-x-user-info-header.md)(待寫,目前整合在本節)。

### 3.2 Response 攔截器

```ts
// 簡化示意
requestClient.interceptors.response.use(
  (response) => {
    const { code, data, message } = response.data;

    if (code === 0) {
      return data; // 業務成功,只回 data
    }

    // 業務錯誤
    ElMessage.error(message || '操作失敗');
    return Promise.reject(new Error(message));
  },
  (error) => {
    // HTTP 層錯誤
    if (error.response?.status === 401) {
      handleUnauthorized(); // 清 token + 跳中台
    } else if (error.code === 'ECONNABORTED') {
      ElMessage.error('請求逾時,請稍後再試');
    } else {
      ElMessage.error(error.response?.data?.message || '網路錯誤');
    }
    return Promise.reject(error);
  },
);
```

**錯誤分類**

| 來源 | 表現 | 處理 |
| --- | --- | --- |
| Business `code !== 0` | response 200 但 body 標記失敗 | ElMessage.error + reject |
| HTTP 401 | JWT 失效 | 清 state + 跳中台 |
| HTTP 403 | IP 不在白名單 | ElMessage.error,通常不會發生(內網) |
| HTTP 4xx 其他 | Validation / Not found | ElMessage.error |
| HTTP 5xx | 後端炸了 | ElMessage.error,reject |
| Timeout | 慢於 axios timeout | ElMessage.error |
| Network | 完全打不到 | ElMessage.error |

詳細的 401 處理見 [user-flow.md 第 4 節](./user-flow.md#4-token-失效流程)。

---

## 4. SSO 隱身代理

中台真實位址(可能是內網 `MiddlePlatform`,或不對外的 internal domain)**不能讓瀏覽器看到**。

**解法**:Nginx 反向代理把 `/api-sso/*` 在伺服器內部轉到中台。

### 4.1 Nginx 設定(部分節錄)

```nginx
# scripts/deploy/nginx.conf
server {
    listen 80;

    # SSO 隱身代理
    location /api-sso/ {
        # 中台真實位址,瀏覽器看不到
        proxy_pass MiddlePlatform/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }

    # EDM Backend 代理
    location /api/ {
        proxy_pass http://edm-backend/api/;
        # 同上 header 設定
    }

    # 前端靜態檔
    location / {
        root /usr/share/nginx/html;
        try_files $uri $uri/ /index.html;
    }
}
```

### 4.2 前端視角

```ts
// 前端永遠用 /api-sso/...,不知道 MiddlePlatform 存在
const result = await requestClient.post('/api-sso/edm/sso/verify-token', {
  token: jwtFromUrl,
});
```

### 4.3 環境變數對應

| 變數 | 用途 | dev 預設 | prod / uat |
| --- | --- | --- | --- |
| `VITE_HWS_URL` | 中台登入頁(redirect 用) | `MiddlePlatform 登入頁` | 中台對外網址 |
| `VITE_EDM_URL` | 本系統的對外網址(redirect 回來時用) | `EdmFront/` | EDM 對外網址 |
| `VITE_SSO_VERIFY_URL` | 前端打的虛擬路徑(經 nginx 代理) | `/api-sso/edm/sso/verify-token` | 同左 |
| `VITE_PROXY_API_TARGET` | Vite dev server 代理 target(不經 nginx) | `EdmBackend` | — |
| `VITE_PROXY_SSO_TARGET` | 同上,SSO 用 | `MiddlePlatform/` | — |

**dev mode 的代理機制不同** — Vite dev server 自己代理(`vite.config.ts` 的 `server.proxy`),不經 nginx。production 才走 nginx。

---

## 5. 整合對應表

把所有 EDM Backend endpoint 跟前端模組對應起來,方便追溯:

| 前端模組 | 路徑 | 主要 API |
| --- | --- | --- |
| 群組管理 | `views/group/` | `/api/edm/group/{list,view,create,editStatus,getEventList}` |
| 人員管理 | `views/member/` | `/api/edm/member/{list,view,add,editStatus,editEmail,editMobile,editSales}` |
| 活動列表 | `views/event/list/` | `/api/edm/event/list` |
| 活動建立 | `views/event/create/` | `/api/edm/event/{create,imageUpload}` |
| 活動詳細 | `views/event/detail/` | `/api/edm/event/{view,update,getInviteList,importGroup}` |
| Google Form | `views/event/google-form/` | `/api/edm/event/{createGoogleForm,updateGoogleForm,delGoogleForm,getGoogleForm,updateResponseStatus}` |
| 邀請信寄送 | `views/event/invite/` | `/api/edm/mail/inviteMail` |
| 數據分析 | `views/analytics/` | `/api/edm/event/getGoogleForm`(含 stats) |
| SSO 流程 | `bootstrap.ts` + `auth/store` | `/api-sso/edm/sso/verify-token`(經 nginx → 中台) |

> **新增 endpoint 時**:在 `apps/web-ele/src/api/<module>/` 下加對應的 method 檔,export 出去後在 view 裡 import 用。**不要直接寫 axios call**。

---

## 6. 速率限制 / Retry 策略

| 策略 | 現況 | Roadmap |
| --- | --- | --- |
| 業務 API retry | **無** | 對「非寫入」操作可加 retry 1 次 |
| Network timeout | Axios 預設(視 `timeout` 設定) | 統一抓 30s |
| Loading 顯示 | 個別頁面自己控制 | 抽出 `<PageLoading>` 元件統一 |
| 重複呼叫防抖 | **無** | 對「寄信」這類重操作加 button disabled + 5 秒冷卻 |

---

## 7. 跨來源限制 (CORS)

**EDM Frontend 不會遇到 CORS 問題**,因為:

- 前端 → nginx 是同源(同網域)
- nginx → 中台 / 後端是 server-side(不受 CORS 限制)

如果未來把 nginx 拿掉、前端直接 cross-origin 打中台 / 後端,就要中台 / 後端開 CORS,參數對應後端 `EDM_FRONTEND_URL` 環境變數。

---

## 8. 已知整合限制

| 限制 | 影響 | 緩解 |
| --- | --- | --- |
| `X-User-Info` 是 client 自填的 | 後端不應該信任這個 header,要以 JWT 為準 | 約定:`X-User-Info` 只是 metadata 加速,**身分以 JWT 為唯一來源** |
| 無 refresh token | Access 過期 = 重登 | 等中台支援 refresh token |
| 無離線 / queue | 沒網路時操作丟失 | 不在 scope,純線上系統 |
| 無 request signing | 中間人攻擊風險(內網理論上沒有,但 prod 應該配 HTTPS) | 部署時強制 TLS,nginx 設 `ssl_protocols TLSv1.2+` |

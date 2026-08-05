# 公网部署手册

本手册同时覆盖 Render 免费短期测试、Render 正式托管部署和自管 Linux 部署。根目录的 `render.yaml` 使用 Free Web Service 与 Free PostgreSQL，不创建付费磁盘，也不要求绑定银行卡；它仅适合少量同学短期测试。Free Web 闲置约 15 分钟会休眠，本地上传文件会在休眠、重启或重新部署后丢失，Free PostgreSQL 固定 1GB 且约 30 天后到期、没有托管备份。`render.production.yaml` 单独保留未来正式付费部署规格，除非在 Render 中明确选择该文件，否则不会创建任何收费资源。

## 0. 推荐路径：GitHub 一键部署到 Render

仓库已经包含 `Dockerfile`、`.dockerignore`、`render.yaml`、`render.production.yaml` 和 GitHub Actions。Render 会从 Dockerfile 构建。免费配置在容器启动时执行迁移和幂等管理员初始化；正式配置在发布前执行同样的命令，并通过 `/healthz` 判断是否健康。

### 第一步：推送 GitHub

在项目根目录执行：

```bash
git init
git add .
git commit -m "Prepare production deployment"
git branch -M main
git remote add origin https://github.com/<你的账号>/suzhou-campus-hub.git
git push -u origin main
```

GitHub 仓库建议设为私有。确认 Actions 页的 `Test and build` 通过；它会运行全部 pytest 测试并构建 Docker 镜像。

### 第二步：创建 Render Blueprint

1. 登录 Render，选择 **New → Blueprint**。
2. 连接上一步的 GitHub 仓库，Render 会自动读取根目录的 `render.yaml`。
3. 为三个 `sync: false` 的密钥填写真实值：
   - `ADMIN_EMAIL`：首个管理员邮箱
   - `ADMIN_NICKNAME`：至少 2 个字符
   - `ADMIN_PASSWORD`：至少 12 个字符的独立强密码
4. 第一阶段测试应确认只创建 `suzhou-campus-hub` Free Web Service 与 `suzhou-campus-hub-db` Free PostgreSQL，不创建持久化磁盘。如果页面要求银行卡或显示 Starter、Basic、Pro 等付费规格，立即取消。
5. 点击 **Apply**。首次构建通常需要几分钟；免费实例会休眠，首次唤醒可能明显变慢。

`SECRET_KEY` 由 Render 生成；`DATABASE_URL` 从数据库内网地址自动注入；`APP_BASE_URL` 自动读取 Render 提供的 `RENDER_EXTERNAL_URL`。不要把真实密钥写入仓库。

### 第三步：验收公开地址

Render 服务状态变为 Live 后，打开服务页顶部的 `https://<服务名>.onrender.com`。依次验证：

```text
https://<服务名>.onrender.com/healthz
https://<服务名>.onrender.com/
https://<服务名>.onrender.com/auth/login
```

`/healthz` 必须返回 `{"database":"reachable","status":"ok"}`。用手机关闭 Wi-Fi 后通过蜂窝网络再打开首页，排除仅局域网可访问的情况。Render 对 Web Service 自动将 HTTP 重定向到 HTTPS并提供 TLS。

### 第四步：首发后的安全操作

1. 使用 `ADMIN_EMAIL` 和 `ADMIN_PASSWORD` 登录后台，立即确认管理员可用。
2. 管理员已创建后，可以从 Render 密钥设置中移除 `ADMIN_PASSWORD`；后续 `bootstrap-admin` 检测到管理员已存在会安全退出。
3. 保持 `FEATURE_TUTORING_PUBLIC=False`。
4. 不要在生产环境运行 `flask seed` 或 `flask seed --reset`。
5. 在 Render PostgreSQL 的 Recovery 页面启用并验证 PITR，另做定期逻辑导出。

### 自定义域名

在 Render 服务的 **Settings → Custom Domains** 添加域名，再按提示配置 DNS。Render 会自动签发与续期 TLS 证书，并把 HTTP 重定向到 HTTPS。域名生效后设置 `APP_BASE_URL=https://你的域名` 并重新部署，使调查二维码使用正式域名。

## 1. 公开与校内访问边界

公网可直接访问：首页、关于与法律页面、注册登录、健康检查，以及管理员明确允许匿名的已发布调查。

以下校内内容由服务端强制要求“已登录且学生认证通过”，仅隐藏导航不能替代权限检查：

- 信息广场、帖子详情、评论、收藏和举报
- 新生指南、FAQ、校园地图
- 全英课堂助手、学习资源和经验投稿
- 用户中心与个人参与记录

管理员继续使用独立角色检查。待认证账号登录后仍不能读取校内内容。

## 2. 生产环境要求

- Python 3.12+
- PostgreSQL 15+（建议使用托管数据库）
- Nginx 或云负载均衡器负责 HTTPS
- Gunicorn 运行 Flask；不要使用 `flask run` 对公网服务
- 域名、有效 TLS 证书和只能由运维访问的环境变量/密钥管理

安装：

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 3. 环境变量

以 `.env.production.example` 为清单，把真实值写入部署平台密钥管理、systemd `EnvironmentFile` 或权限为 `600` 的服务器文件。不要提交 `.env`。

生成密钥：

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

生产模式会拒绝以下不安全配置并停止启动：

- 缺少或少于 32 字符的 `SECRET_KEY`
- 非 PostgreSQL 的 `DATABASE_URL`
- 不以 `https://` 开头的 `APP_BASE_URL`

常见托管平台给出的 `postgres://` 和 `postgresql://` 会自动规范为 psycopg 3 驱动地址。

## 4. PostgreSQL 初始化

先创建最小权限的数据库与账号，再设置 `DATABASE_URL`。应用账号只需目标数据库的连接、表和序列权限，不应拥有 PostgreSQL 超级用户权限。

首次发布：

```bash
export APP_ENV=production
flask --app wsgi.py db upgrade
flask --app wsgi.py bootstrap-admin
```

其中 `bootstrap-admin` 从 `ADMIN_EMAIL`、`ADMIN_NICKNAME`、`ADMIN_PASSWORD` 读取首个管理员信息，重复执行不会重复创建。人工交互部署也可使用 `flask --app wsgi.py create-admin`。

生产环境不要运行 `flask seed --reset`，演示账号和演示密码不应出现在公网实例。

已有真实用户数据后的发布顺序：使用 `pg_dump` 导出到数据库之外并验证备份 → 安装依赖 → `flask db upgrade` → 重启应用 → 检查 `/healthz`。空数据库的首次测试部署可以跳过备份。数据库迁移只运行一次，不要让每个 worker 同时执行，也不得用同一数据库中的复制表冒充正式备份。

## 5. Gunicorn

项目已包含 `wsgi.py`、`gunicorn.conf.py` 和 `Procfile`：

```bash
gunicorn -c gunicorn.conf.py wsgi:app
```

本地直接运行 Gunicorn 默认 3 个 gthread worker、每个 2 个线程。`render.yaml` 的 Free Web Service 配置 2 个 worker、每个 4 个线程，只用于少量同学短期验收，不承诺 300 人长期稳定并发。数据库连接理论上限约为 `WEB_CONCURRENCY × (DB_POOL_SIZE + DB_MAX_OVERFLOW)`；Render 免费配置上限约 20，必须低于托管 PostgreSQL 的连接上限并为迁移和管理连接留余量。正式上线应改用 `render.production.yaml` 或等价的付费生产资源并重新压测。

## 6. Nginx HTTPS 反向代理

Gunicorn 只监听 `127.0.0.1:8000`，防火墙不得直接开放该端口。Nginx 示例：

```nginx
server {
    listen 80;
    server_name campus.example.com;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    server_name campus.example.com;

    ssl_certificate /etc/letsencrypt/live/campus.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/campus.example.com/privkey.pem;

    client_max_body_size 5m;

    location /static/ {
        alias /srv/campus-hub/app/static/;
        expires 7d;
    }

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Forwarded-Port $server_port;
        proxy_read_timeout 30s;
    }
}
```

只有应用恰好位于一个可信反向代理之后时才设置 `TRUST_PROXY=True`。应用使用 `ProxyFix(..., x_for=1, x_proto=1, x_host=1, x_port=1)`，错误的代理层数会让客户端伪造转发头。

生产配置启用 Secure/HttpOnly/SameSite Cookie、HSTS、CSP、禁止 iframe、MIME 嗅探和敏感浏览器权限。TLS 终止后应用根据可信的 `X-Forwarded-Proto` 识别 HTTPS。

## 7. systemd 示例

```ini
[Unit]
Description=Suzhou Campus Hub
After=network.target postgresql.service

[Service]
User=campushub
Group=campushub
WorkingDirectory=/srv/campus-hub
EnvironmentFile=/etc/campus-hub.env
ExecStart=/srv/campus-hub/.venv/bin/gunicorn -c gunicorn.conf.py wsgi:app
Restart=always
RestartSec=5
PrivateTmp=true
NoNewPrivileges=true

[Install]
WantedBy=multi-user.target
```

## 8. 上传文件

当前图片存储在 `UPLOAD_FOLDER`。免费 `render.yaml` 不创建持久化磁盘，因此上传文件会在休眠、重启或重新部署后丢失；第一阶段只能把上传能力视为临时验收功能。正式上线使用 `render.production.yaml` 时会挂载 1GB 持久化磁盘，且必须将磁盘与数据库分别备份。Docker 镜像和 Git 仓库均排除真实上传文件。

Render 的单个持久化磁盘限制服务为单实例。若需要多实例或自动扩缩容，应先迁移到兼容 S3 的对象存储，并继续只在数据库保存随机化后的对象键。对象存储应启用私有桶、服务端加密、版本控制、生命周期策略和最小权限凭据。

## 9. 日志

应用把日志写到 stdout/stderr，由容器平台收集。Gunicorn 原始访问日志已关闭，Flask 只记录请求 ID、方法、路径、状态码和耗时，不记录查询参数、请求正文、Cookie、联系方式或完整 IP。`X-Request-ID` 可用于关联单次请求；不要把 `LOG_LEVEL` 长期设为 `DEBUG`。

## 10. 发布检查

- 本次调查结果升级包含数据库迁移；当前没有真实用户数据的首次测试部署可直接执行 `flask db upgrade`。以后已有真实数据时，必须先按备份文档完成数据库外部的可验证备份，并在隔离数据库验证恢复
- 专业代码迁移会新增受约束的 `major_code` 字段，并把无法确定具体归属的历史合并记录标记为“待确认”；迁移不会猜测用户专业，也不会创建 `backup_*`、`shadow_*` 或其他同库复制表
- `/healthz` 返回 200 且数据库为 `reachable`
- 匿名访问校内路由会跳转登录
- 仅持有效邀请码注册且社区权限正常的用户可以读取校内内容；管理员可撤销或停用账号
- 已认证学生可以访问，普通学生不能进入管理后台
- HTTPS 跳转、Secure Cookie、HSTS 和安全响应头正常
- 数据库备份成功且完成过恢复演练
- 日志不包含密码、家长联系方式、调查联系方式或完整 IP

更完整的备份操作见 `docs/BACKUP_AND_RESTORE.md`。

# 数据库备份与恢复方案

## 目标

生产数据以 PostgreSQL 为唯一权威数据源。建议恢复点目标（RPO）不超过 24 小时，恢复时间目标（RTO）不超过 4 小时；上线后根据真实使用频率提高到连续归档或托管数据库 PITR。

## PostgreSQL 备份

Render 的付费 PostgreSQL 提供连续时间点恢复（PITR）。Hobby workspace 的恢复窗口为 3 天，Pro 或更高 workspace 为 7 天；Free 数据库没有恢复能力，不得用于本项目生产环境。PITR 不能替代长期异地副本：每周至少创建一次逻辑导出并下载到受控的加密存储。

每天低峰期执行一次自定义格式逻辑备份：

```bash
umask 077
mkdir -p /var/backups/campus-hub
pg_dump --format=custom --no-owner --no-acl \
  --file="/var/backups/campus-hub/campus_hub_$(date +%Y%m%d_%H%M).dump" \
  "$DATABASE_URL"
```

不要把数据库密码写进脚本或命令历史。定时任务应从受限环境文件或云密钥管理读取 `DATABASE_URL`。

建议保留策略：

- 每日备份保留 7 天
- 每周备份保留 4 周
- 每月备份保留 12 个月
- 至少一份加密副本存放在不同故障域或对象存储

备份完成后检查文件非空并运行：

```bash
pg_restore --list /var/backups/campus-hub/campus_hub_YYYYMMDD_HHMM.dump > /dev/null
```

## 恢复演练

至少每季度在隔离的临时数据库执行一次：

```bash
createdb campus_hub_restore_test
pg_restore --clean --if-exists --no-owner --no-acl \
  --dbname=campus_hub_restore_test \
  /var/backups/campus-hub/campus_hub_YYYYMMDD_HHMM.dump
```

恢复后验证：

- `flask db current` 与仓库迁移 head 一致
- 用户、帖子、调查和答卷数量合理
- `/healthz`、登录、受保护内容和管理员页面正常
- 导出文件可生成且中文正常

验证后删除临时恢复数据库。不要把恢复演练连接到生产域名。

## 迁移前备份与回滚

每次 `flask db upgrade` 前创建备份并记录当前迁移版本。应用代码回滚不等于数据库自动降级；除非迁移已经在副本验证，生产环境不要直接运行 `flask db downgrade`。优先恢复上一版本应用兼容性或从已验证备份恢复。

## SQLite 本地备份

本地开发数据库可以使用 SQLite 在线备份命令，避免直接复制正在写入的数据库文件：

```powershell
sqlite3 instance\campus_hub.db ".backup 'instance\backups\campus_hub_backup.db'"
```

本地演示数据可由 `flask db upgrade` 和 `flask seed --reset` 重建；生产 PostgreSQL 绝不能依赖 Seed 代替备份。

## 上传文件

数据库备份不包含 `app/static/uploads`。Render 持久化磁盘需单独做文件级备份，并使其时间点尽量与数据库备份一致。最低建议：每日增量、每周完整副本、至少一份加密异地副本；每季度抽样恢复图片并核对数据库引用。未来迁移对象存储后，应开启版本控制、生命周期规则和服务端加密。

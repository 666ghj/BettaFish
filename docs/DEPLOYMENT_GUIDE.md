# BettaFish 部署运维手册

**文档版本**: 1.0.0
**最后更新**: 2025-11-15
**适用场景**: 生产环境部署、运维管理

---

## 部署方案对比

| 方案 | 难度 | 性能 | 可维护性 | 适用场景 |
|------|------|------|----------|----------|
| **Docker Compose** | ⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | 开发/测试/小规模生产 |
| **源码部署** | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | 定制化需求 |
| **Kubernetes** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | 大规模生产环境 |

---

## 方案1: Docker Compose部署 (推荐)

### 系统要求

- **操作系统**: Linux (Ubuntu 20.04+, CentOS 7+), macOS, Windows 10+
- **Docker**: 20.10+
- **Docker Compose**: 1.29+
- **内存**: 最低4GB, 推荐8GB+
- **磁盘**: 最少10GB可用空间
- **CPU**: 2核+, 推荐4核+

### 快速部署 (5分钟)

```bash
# 1. 安装Docker和Docker Compose (如果未安装)
# Ubuntu/Debian
curl -fsSL https://get.docker.com | bash
sudo usermod -aG docker $USER
newgrp docker

# CentOS/RHEL
sudo yum install -y docker docker-compose
sudo systemctl start docker
sudo systemctl enable docker

# 2. 克隆仓库
git clone https://github.com/666ghj/BettaFish.git
cd BettaFish

# 3. 配置环境变量
cp .env.example .env
nano .env  # 编辑配置

# 4. 启动服务
docker compose up -d

# 5. 查看日志
docker compose logs -f bettafish

# 6. 检查状态
docker compose ps
```

### 访问应用

- **Flask主应用**: http://localhost:5000
- **Insight Engine**: http://localhost:8501
- **Media Engine**: http://localhost:8502
- **Query Engine**: http://localhost:8503
- **PostgreSQL**: localhost:5444

### 常用命令

```bash
# 停止服务
docker compose down

# 停止并删除数据卷
docker compose down -v

# 重启服务
docker compose restart

# 查看日志
docker compose logs -f [service_name]

# 进入容器
docker compose exec bettafish bash

# 更新镜像
docker compose pull
docker compose up -d
```

### 配置说明

**必需配置** (`.env`):

```bash
# 数据库配置
DB_HOST=db                    # 容器名称
DB_PORT=5432
DB_USER=bettafish
DB_PASSWORD=bettafish
DB_NAME=bettafish
DB_DIALECT=postgresql

# LLM API密钥 (至少配置一个)
INSIGHT_ENGINE_API_KEY=sk-xxx
INSIGHT_ENGINE_BASE_URL=https://api.moonshot.cn/v1
INSIGHT_ENGINE_MODEL_NAME=kimi-k2-0711-preview

# 网络搜索 (可选)
TAVILY_API_KEY=tvly-xxx
BOCHA_WEB_SEARCH_API_KEY=xxx
```

### 持久化数据

**数据卷映射**:

```yaml
# docker-compose.yml
volumes:
  - ./logs:/app/logs                    # 运行日志
  - ./final_reports:/app/final_reports  # 生成报告
  - ./.env:/app/.env                    # 配置文件
  - ./db_data:/var/lib/postgresql/data  # 数据库数据
```

**备份数据库**:

```bash
# 导出数据库
docker compose exec db pg_dump -U bettafish bettafish > backup.sql

# 恢复数据库
docker compose exec -T db psql -U bettafish bettafish < backup.sql
```

---

## 方案2: 源码部署

### 系统要求

- **操作系统**: Linux, macOS, Windows
- **Python**: 3.9-3.11
- **数据库**: PostgreSQL 12+ 或 MySQL 5.7+
- **内存**: 最低2GB, 推荐4GB+

### 详细步骤

#### 1. 安装系统依赖

**Ubuntu/Debian**:

```bash
sudo apt update
sudo apt install -y \
    python3.11 python3.11-venv python3-pip \
    postgresql postgresql-contrib \
    build-essential curl git \
    libgl1 libglib2.0-0 ffmpeg
```

**CentOS/RHEL**:

```bash
sudo yum install -y \
    python311 python311-devel \
    postgresql-server postgresql-contrib \
    gcc make curl git
```

#### 2. 安装PostgreSQL

```bash
# 初始化数据库 (CentOS)
sudo postgresql-setup initdb

# 启动服务
sudo systemctl start postgresql
sudo systemctl enable postgresql

# 创建数据库和用户
sudo -u postgres psql
CREATE DATABASE bettafish;
CREATE USER bettafish WITH PASSWORD 'your_secure_password';
GRANT ALL PRIVILEGES ON DATABASE bettafish TO bettafish;
ALTER USER bettafish WITH SUPERUSER;
\q
```

#### 3. 创建Python环境

```bash
# 使用venv
python3.11 -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate   # Windows

# 或使用Conda
conda create -n bettafish python=3.11
conda activate bettafish
```

#### 4. 安装Python依赖

```bash
# 基础依赖
pip install -r requirements.txt

# 安装Playwright浏览器
playwright install chromium
```

#### 5. 配置应用

```bash
# 创建配置文件
cp .env.example .env

# 编辑配置
nano .env
```

**关键配置**:

```bash
# 数据库
DB_DIALECT=postgresql
DB_HOST=localhost
DB_PORT=5432
DB_USER=bettafish
DB_PASSWORD=your_secure_password
DB_NAME=bettafish

# LLM API
INSIGHT_ENGINE_API_KEY=sk-xxx
# ... 其他配置
```

#### 6. 启动应用

```bash
# 激活虚拟环境
source venv/bin/activate

# 启动Flask应用
python app.py
```

### 使用Systemd管理 (推荐)

**创建服务文件**: `/etc/systemd/system/bettafish.service`

```ini
[Unit]
Description=BettaFish Multi-Agent System
After=network.target postgresql.service
Wants=postgresql.service

[Service]
Type=simple
User=www-data
Group=www-data
WorkingDirectory=/var/www/BettaFish

# 使用虚拟环境的Python
Environment="PATH=/var/www/BettaFish/venv/bin:/usr/local/bin:/usr/bin"
Environment="PYTHONUNBUFFERED=1"

ExecStart=/var/www/BettaFish/venv/bin/python app.py

Restart=always
RestartSec=10

# 日志
StandardOutput=journal
StandardError=journal
SyslogIdentifier=bettafish

[Install]
WantedBy=multi-user.target
```

**启用服务**:

```bash
sudo systemctl daemon-reload
sudo systemctl enable bettafish
sudo systemctl start bettafish
sudo systemctl status bettafish
```

**查看日志**:

```bash
# 实时日志
sudo journalctl -u bettafish -f

# 最近100行
sudo journalctl -u bettafish -n 100
```

---

## 生产环境优化

### 1. Nginx反向代理

**安装Nginx**:

```bash
sudo apt install nginx  # Ubuntu
sudo yum install nginx  # CentOS
```

**配置文件**: `/etc/nginx/sites-available/bettafish`

```nginx
upstream flask_backend {
    server localhost:5000;
}

upstream streamlit_insight {
    server localhost:8501;
}

upstream streamlit_media {
    server localhost:8502;
}

upstream streamlit_query {
    server localhost:8503;
}

server {
    listen 80;
    server_name your-domain.com;

    # 强制HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name your-domain.com;

    # SSL证书
    ssl_certificate /etc/letsencrypt/live/your-domain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/your-domain.com/privkey.pem;

    # SSL优化
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;

    # Flask主应用
    location / {
        proxy_pass http://flask_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # WebSocket支持
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_read_timeout 86400;
    }

    # Streamlit应用
    location /insight/ {
        proxy_pass http://streamlit_insight/;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_read_timeout 86400;
    }

    location /media/ {
        proxy_pass http://streamlit_media/;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }

    location /query/ {
        proxy_pass http://streamlit_query/;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }

    # 静态文件
    location /static/ {
        alias /var/www/BettaFish/static/;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }

    # 日志
    access_log /var/log/nginx/bettafish_access.log;
    error_log /var/log/nginx/bettafish_error.log;
}
```

**启用配置**:

```bash
sudo ln -s /etc/nginx/sites-available/bettafish /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

### 2. SSL证书 (Let's Encrypt)

```bash
# 安装Certbot
sudo apt install certbot python3-certbot-nginx

# 自动配置SSL
sudo certbot --nginx -d your-domain.com

# 自动续期
sudo certbot renew --dry-run
```

### 3. 数据库优化

**PostgreSQL配置**: `/etc/postgresql/15/main/postgresql.conf`

```ini
# 内存配置 (假设8GB总内存)
shared_buffers = 2GB
effective_cache_size = 6GB
work_mem = 16MB
maintenance_work_mem = 512MB

# 连接配置
max_connections = 200

# 查询优化
random_page_cost = 1.1  # SSD
effective_io_concurrency = 200

# WAL配置
wal_buffers = 16MB
checkpoint_completion_target = 0.9

# 日志
logging_collector = on
log_directory = 'pg_log'
log_filename = 'postgresql-%Y-%m-%d_%H%M%S.log'
log_rotation_age = 1d
log_min_duration_statement = 1000  # 记录慢查询
```

**重启生效**:

```bash
sudo systemctl restart postgresql
```

### 4. 日志管理

**Logrotate配置**: `/etc/logrotate.d/bettafish`

```
/var/www/BettaFish/logs/*.log {
    daily
    rotate 30
    compress
    delaycompress
    notifempty
    create 0640 www-data www-data
    sharedscripts
    postrotate
        systemctl reload bettafish > /dev/null 2>&1 || true
    endscript
}
```

---

## 监控与告警

### 1. 系统监控 (Prometheus + Grafana)

**安装Prometheus**:

```bash
# 下载
wget https://github.com/prometheus/prometheus/releases/download/v2.40.0/prometheus-2.40.0.linux-amd64.tar.gz
tar xvfz prometheus-2.40.0.linux-amd64.tar.gz
cd prometheus-2.40.0.linux-amd64

# 配置prometheus.yml
cat > prometheus.yml <<EOF
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'bettafish'
    static_configs:
      - targets: ['localhost:5000']
  - job_name: 'postgres'
    static_configs:
      - targets: ['localhost:9187']
EOF

# 启动
./prometheus --config.file=prometheus.yml
```

### 2. 应用监控

**添加健康检查端点**:

```python
# app.py
@app.route('/health')
def health_check():
    """健康检查"""
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "v1.2.1",
        "agents": {
            "insight": processes['insight']['status'],
            "media": processes['media']['status'],
            "query": processes['query']['status'],
        }
    })

@app.route('/metrics')
def metrics():
    """Prometheus metrics"""
    # 返回Prometheus格式的指标
    pass
```

### 3. 邮件告警

```python
# 添加邮件告警
import smtplib
from email.mime.text import MIMEText

def send_alert(subject: str, message: str):
    msg = MIMEText(message)
    msg['Subject'] = f"[BettaFish Alert] {subject}"
    msg['From'] = "alert@your-domain.com"
    msg['To'] = "admin@your-domain.com"

    with smtplib.SMTP('smtp.gmail.com', 587) as server:
        server.starttls()
        server.login("your-email@gmail.com", "your-password")
        server.send_message(msg)
```

---

## 备份与恢复

### 数据库备份

**自动备份脚本**: `/usr/local/bin/backup-bettafish.sh`

```bash
#!/bin/bash

# 配置
BACKUP_DIR="/var/backups/bettafish"
DB_NAME="bettafish"
DB_USER="bettafish"
DATE=$(date +%Y%m%d_%H%M%S)

# 创建备份目录
mkdir -p $BACKUP_DIR

# 备份数据库
pg_dump -U $DB_USER $DB_NAME | gzip > $BACKUP_DIR/db_backup_$DATE.sql.gz

# 备份文件
tar -czf $BACKUP_DIR/files_backup_$DATE.tar.gz \
    /var/www/BettaFish/final_reports \
    /var/www/BettaFish/logs \
    /var/www/BettaFish/.env

# 保留最近30天的备份
find $BACKUP_DIR -name "*.gz" -mtime +30 -delete

echo "Backup completed: $DATE"
```

**设置Cron**:

```bash
# 编辑crontab
crontab -e

# 添加每天凌晨2点备份
0 2 * * * /usr/local/bin/backup-bettafish.sh >> /var/log/bettafish-backup.log 2>&1
```

### 恢复数据

```bash
# 恢复数据库
gunzip -c /var/backups/bettafish/db_backup_20251115_020000.sql.gz | \
    psql -U bettafish bettafish

# 恢复文件
tar -xzf /var/backups/bettafish/files_backup_20251115_020000.tar.gz -C /
```

---

## 故障排查

### 常见问题

**1. Flask应用无法启动**

```bash
# 检查日志
sudo journalctl -u bettafish -n 100

# 检查端口占用
sudo lsof -i :5000

# 检查Python环境
which python
python --version
```

**2. Agent启动失败**

```bash
# 检查Streamlit进程
ps aux | grep streamlit

# 手动启动测试
streamlit run SingleEngineApp/insight_engine_streamlit_app.py --server.port 8501
```

**3. 数据库连接错误**

```bash
# 测试连接
psql -h localhost -U bettafish -d bettafish

# 检查PostgreSQL状态
sudo systemctl status postgresql

# 查看PostgreSQL日志
sudo tail -f /var/log/postgresql/postgresql-15-main.log
```

**4. 内存不足**

```bash
# 检查内存使用
free -h
top

# 添加swap
sudo fallocate -l 4G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
```

---

## 性能调优

### 1. 应用层优化

```python
# 使用Gunicorn + Uvicorn workers (生产环境)
pip install gunicorn uvicorn

# 启动
gunicorn app:app \
    -w 4 \  # 4个worker进程
    -k uvicorn.workers.UvicornWorker \
    --bind 0.0.0.0:5000 \
    --timeout 300 \
    --access-logfile - \
    --error-logfile -
```

### 2. 数据库查询优化

```sql
-- 创建必要的索引
CREATE INDEX CONCURRENTLY idx_posts_topic_time ON weibo_posts(topic_id, post_time DESC);
CREATE INDEX CONCURRENTLY idx_comments_post ON weibo_comments(post_id);

-- 分析表统计信息
ANALYZE weibo_posts;
ANALYZE weibo_comments;
```

### 3. 缓存策略

```python
# 使用Redis缓存热点数据
import redis

cache = redis.Redis(host='localhost', port=6379, db=0)

def get_hot_topics(time_period: str):
    cache_key = f"hot_topics:{time_period}"

    # 尝试从缓存获取
    cached = cache.get(cache_key)
    if cached:
        return json.loads(cached)

    # 查询数据库
    results = db.query(...)

    # 写入缓存(5分钟过期)
    cache.setex(cache_key, 300, json.dumps(results))

    return results
```

---

## 安全加固

### 1. 防火墙配置

```bash
# Ubuntu (UFW)
sudo ufw allow 22/tcp    # SSH
sudo ufw allow 80/tcp    # HTTP
sudo ufw allow 443/tcp   # HTTPS
sudo ufw enable

# CentOS (firewalld)
sudo firewall-cmd --permanent --add-service=http
sudo firewall-cmd --permanent --add-service=https
sudo firewall-cmd --reload
```

### 2. SSH安全

```bash
# /etc/ssh/sshd_config
PermitRootLogin no
PasswordAuthentication no
PubkeyAuthentication yes

sudo systemctl restart sshd
```

### 3. 限制PostgreSQL访问

```bash
# /etc/postgresql/15/main/pg_hba.conf
# 只允许本地连接
local   all             all                                     peer
host    all             all             127.0.0.1/32            md5
host    all             all             ::1/128                 md5
```

---

## 更新与升级

### 应用更新

```bash
# 1. 备份
/usr/local/bin/backup-bettafish.sh

# 2. 拉取最新代码
cd /var/www/BettaFish
git pull origin main

# 3. 更新依赖
source venv/bin/activate
pip install -r requirements.txt --upgrade

# 4. 重启服务
sudo systemctl restart bettafish

# 5. 检查状态
sudo systemctl status bettafish
```

### Docker更新

```bash
cd /path/to/BettaFish

# 拉取最新镜像
docker compose pull

# 重启服务
docker compose up -d

# 清理旧镜像
docker image prune -a
```

---

**文档维护**: BettaFish运维团队
**更新日期**: 2025-11-15

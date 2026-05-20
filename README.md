# Motion Sprite Studio

> UI 优化版：修复了页面横向溢出导致左侧大面积空白、视频原生控制被裁剪层遮挡、拖拽裁剪与预览不同步等问题；增加了自定义播放控制条。

一个面向游戏素材制作的“视频转序列帧 / 精灵图 / GIF / Spine 基础包”工具。

本项目是一个 Python 后端增强的视频序列帧处理工具：

- 前端：Vite + React + TypeScript
- 后端：FastAPI + OpenCV + Pillow + ImageIO
- 处理模式：单任务队列、逐帧处理、逐帧落盘，适合 4G 内存云服务器自用部署
- 输出：透明 PNG 序列 ZIP、sprite sheet、GIF、Spine JSON + PNG ZIP、处理报告

> 原项目是 GPL-3.0-only 授权。如果你把本项目作为原项目的派生版本继续分发，建议同样按 GPL-3.0-only 处理授权。

---

## 功能

- 上传本地视频
- 设置起止时间、FPS、最大帧数
- 画面裁剪：支持前端拖拽框选，也支持数值微调
- 点选视频画面取背景色
- 自定义播放/暂停、时间轴拖动、前后 1 秒微调
- 裁剪预览实时刷新，避免遮挡原生播放器控件
- Python 后端 ChromaKey 抠图
- 容差、柔边、去溢色、Mask 去噪/补洞参数
- 输出普通帧或透明帧
- 导出：
  - `frames.zip`：单帧 PNG 序列
  - `sprite_sheet.png`：精灵图
  - `animation.gif`：动画 GIF
  - `spine.zip`：Spine 基础动画包，含 `skeleton.json` 和 `images/*.png`
  - `report.json`：处理参数和视频信息

---

## 适合的素材

效果最好：

- 绿幕 / 蓝幕 / 白底 / 灰底 / 纯色背景视频
- AI 生成角色动图、游戏角色待机动画、技能动画
- 需要转成 Godot / Spine / 精灵图的短视频素材

不适合：

- 背景复杂的视频
- 主体和背景颜色接近的视频
- 超长视频、4K 视频、大量并发任务

---

## 4G 云服务器建议配置

推荐限制：

```env
VTS_MAX_UPLOAD_MB=200
VTS_MAX_DURATION_SECONDS=60
VTS_MAX_FRAMES=120
VTS_MAX_WIDTH=1920
VTS_MAX_HEIGHT=1080
VTS_WORKERS=1
```

启动时不要开多个 worker：

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1
```

---

## 本地开发启动

### 1. 后端

```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 1 --log-level debug
```

### 2. 前端

```bash
cd frontend
npm install
npm run dev
```

前端默认访问：

```text
http://localhost:5173
```

后端默认地址：

```text
http://localhost:8000
```

---

## 生产部署：Docker 一键启动

服务器需要先安装 Docker / Docker Compose。

```bash
cd motion-sprite-studio
docker compose up -d --build
```

访问：

```text
http://服务器IP:8000
```

默认数据目录：

```text
./data
```

里面会保存上传文件、处理帧和输出结果。你可以定期清理旧任务目录。

---

## Nginx 反向代理示例

参考 `deploy/nginx.example.conf`。

核心配置：

```nginx
location / {
    proxy_pass http://127.0.0.1:8000;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    client_max_body_size 220m;
}
```

---

## Windows 本地快速启动

双击或运行：

```bat
scripts\start-dev.bat
```

Linux / macOS：

```bash
bash scripts/start-dev.sh
```

---

## 常见问题

### 1. 抠图边缘有绿边怎么办？

提高“去溢色”到 0.7-1.0；适当提高柔边；如果主体边缘被吃掉，降低容差。

### 2. 主体被抠掉怎么办？

降低容差；重新点击更准确的背景色；尽量选离主体较远的纯背景区域。

### 3. 4G 内存会不会爆？

默认是逐帧处理并落盘，不会一次性把所有帧加载进内存。仍建议限制最大时长、最大帧数和并发任务数。

### 4. GIF 透明效果不完美？

GIF 透明只有单通道透明，不适合复杂半透明边缘。游戏素材建议优先用 PNG 序列或 sprite sheet。

---

## 目录结构

```text
motion-sprite-studio/
├─ backend/
│  ├─ app/
│  │  ├─ main.py
│  │  ├─ config.py
│  │  ├─ chroma.py
│  │  ├─ processor.py
│  │  ├─ exporter.py
│  │  └─ jobs.py
│  └─ requirements.txt
├─ frontend/
│  ├─ src/
│  │  ├─ App.tsx
│  │  ├─ api.ts
│  │  ├─ types.ts
│  │  ├─ main.tsx
│  │  └─ style.css
│  ├─ package.json
│  └─ vite.config.ts
├─ deploy/
├─ scripts/
├─ Dockerfile
├─ docker-compose.yml
└─ README.md
```

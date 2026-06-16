# Personal Learning Agent 应用版说明

## 1. 应用版定位

Personal Learning Agent 应用版是一个 Windows 桌面程序，入口文件是 `desktop_app.py`。它使用 Tkinter 构建图形界面，适合在本机直接运行，不依赖浏览器页面。

应用版主要用于个人离线记录和轻量 AI 学习助手体验。它和网页版保持相近的视觉风格与核心学习管理逻辑，但数据存储位置、运行方式和部署方式不同。

## 2. 当前可用功能

应用版支持：

- 用户名进入个人空间
- 每日学习日志记录
- 今日计划
- 今日笔记
- 待解决事项
- 明日计划
- 历史记录读取
- 历史关键字搜索
- AI 学习助手
- AI 生成计划
- AI 计划应用到指定日期
- 本地用户数据库隔离

应用版更适合单机使用；网页版更适合服务器部署、多电脑访问和文件数据库管理。

## 3. 数据存储

应用版会把用户数据保存到 Windows 本地应用数据目录：

```text
%LOCALAPPDATA%\PersonalLearningAgent\data\users
```

每个用户会对应一个独立 SQLite 数据库文件：

```text
%LOCALAPPDATA%\PersonalLearningAgent\data\users\用户名.db
```

如果旧版本曾经把用户数据库保存在项目目录：

```text
data/users/
```

应用启动时会尝试把旧数据复制到新的本地应用数据目录。

## 4. AI 配置

应用版 AI Key 读取顺序：

1. `%LOCALAPPDATA%\PersonalLearningAgent\config.json`
2. 项目根目录 `config.local.json`

推荐使用本地应用配置文件：

```text
%LOCALAPPDATA%\PersonalLearningAgent\config.json
```

示例：

```json
{
  "api_key": "你的 API Key",
  "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
  "model": "qwen-plus",
  "temperature": 0.4
}
```



## 5. 本地运行应用版

进入项目根目录：

```bash
cd personal-learning-agent
```

安装依赖：

```bash
python -m pip install -r requirements-desktop.txt
```

启动应用：

```bash
python desktop_app.py
```

## 6. 打包为 Windows EXE

项目提供了打包脚本：

```powershell
.\build_desktop.ps1
```

脚本会执行：

```powershell
python -m pip install -r requirements-desktop.txt
pyinstaller --noconfirm --windowed --onefile --name "PersonalLearningAgent" --icon "assets/app_icon.ico" --add-data "assets;assets" desktop_app.py
```

打包完成后，生成文件位于：

```text
dist\PersonalLearningAgent.exe
```

`d

## 7. 应用版和网页版区别

| 对比项 | 网页版 | 应用版 |
| --- | --- | --- |
| 入口 | `app/main.py` + `frontend/` | `desktop_app.py` |
| 运行方式 | FastAPI 服务 + 浏览器 | Windows 桌面窗口 |
| 访问方式 | `http://IP:端口/` | 本机打开程序 |
| 数据库 | `data/learning_agent.db` | `%LOCALAPPDATA%\PersonalLearningAgent\data\users\用户名.db` |
| 多电脑访问 | 支持，同一服务器即可 | 不支持，默认本机数据 |
| 文件数据库 | 网页版支持 | 当前应用版未实现 |
| Word 导出 | 网页版支持 | 当前应用版未实现 |
| 适合场景 | 部署演示、远程访问、正式网页版 | 本机记录、轻量桌面使用 |


- `dist/`
- `build/`
- `*.spec`
- `__pycache__/`


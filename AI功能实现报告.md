# AI 学习助手功能实现报告

## 1. 模块目标

本次新增的 AI 学习助手用于实现项目中的历史记忆查询和智能规划能力。用户可以在桌面端输入自然语言问题，例如“我这个月项目推进到哪了”“这周怎么安排学习”，系统会先读取本地学习日志，再调用大模型生成总结或计划。

## 2. 本地数据库接入逻辑

项目当前采用本地 SQLite 作为长期记忆存储。每个用户登录后，会根据用户名生成独立数据库文件，保存路径固定在 Windows 用户目录：

```text
C:\Users\当前用户\AppData\Local\PersonalLearningAgent\data\users\用户名.db
```

这样做的原因是：打包成 exe 后，程序所在目录可能变化，但 AppData 是稳定目录，所以保存后的日志不会因为移动 exe 或重新打开程序而丢失。

数据库表为 `learning_logs`，主要字段包括：

```text
date            日志日期
content         今日笔记，包含心情和笔记正文
tasks           今日计划
problems        待解决事项
tomorrow_plan   明日计划
category        分类
status          状态
duration_minutes 耗时
remark          备注
```

程序通过 `LogRepository` 封装数据库操作，主要能力包括：

```text
create()             保存一条日志快照
latest_by_date()     查询某一天最新日志
list_between()       查询某个日期范围内的日志
list_recent()        查询最近若干天日志
search_text()        按关键词检索日志内容
```

## 3. AI 查询的整体流程

AI 助手不是直接把用户问题发给大模型，而是先检索本地记忆，再让大模型基于检索结果回答。

整体流程是：

```text
用户输入问题
 -> 根据问题解析查询范围
 -> 从 SQLite 查询相关日志
 -> 整理日志上下文
 -> 调用 Chat 模型 API
 -> 在右侧回复框展示回答
```

目前支持的规则检索包括：

```text
今天
昨天
上周三
本周 / 这周
本月 / 这个月
最近 / 前几天
Agent / 论文 / 项目 / 计组 / 计网 / 开题等关键词
```

如果问题中没有明显时间或关键词，系统默认读取最近 14 天日志作为上下文。

## 4. 大模型 API 接入方式

代码使用 OpenAI 兼容的 Chat Completions 格式调用模型接口。配置从本地文件读取：

```text
config.local.json
```

配置结构为：

```json
{
  "base_url": "https://api.deepseek.com/chat/completions",
  "model": "deepseek-chat",
  "api_key": "你的 API Key",
  "temperature": 0.4
}
```

`config.local.json` 已加入 `.gitignore`，不会提交到 Git。这样可以避免 API Key 泄露。

模型调用逻辑封装在：

```text
load_llm_config()
call_chat_model()
```

其中 `call_chat_model()` 会：

```text
读取 API Key
构造 HTTP POST 请求
发送 messages
解析 choices[0].message.content
将模型回复返回给界面
```

为了避免系统中错误代理影响请求，HTTP 调用默认不使用环境代理。

## 5. Prompt 构造逻辑

AI 助手会构造两类消息：

```text
system message：定义 AI 是个人学习管理 Agent，要求只能依据日志回答，不要编造。
user message：包含用户问题、检索到的日志上下文、任务要求。
```

如果问题里包含“计划、规划、安排、目标、这周、本周”等词，系统会把任务要求切换为智能规划模式：

```text
根据历史日志、未完成事项和用户目标拆解成具体学习计划。
，任务要具体、可执行。
```

否则使用历史记忆查询模式：

```text
根据检索到的历史日志回答用户问题，先给结论，再列关键依据。
```

## 6. AI 助手界面实现

桌面端新增了 `AI助手` 按钮，位于 `今日の心情` 上方。按钮使用用户提供的图标裁剪生成：

```text
assets/ai_assistant_icon.png
```

点击后打开 AI 弹窗：

```text
左侧：用户向 AI 提问的输入框
右侧：AI 回复展示区域
顶部：图标 + “主人，来聊聊天吧~”
按钮：发送 / 返回
```

弹窗打开后会先绘制一层浅粉色遮罩，再绘制 AI 窗口。因此后面的日志输入内容不会透出来，也不会被误点。

## 7. 当前完成状态

已完成：

```text
AI 助手按钮
AI 助手弹窗
用户提问输入框
AI 回复显示区域
本地日志检索
Prompt 构造
Chat 模型 API 调用
API Key 本地配置
图标替换
弹窗遮罩
```

暂未重新打包，因为当前阶段需要先验收源码运行效果。

## 8. 后续可扩展方向

后续可以继续增强：

```text
加入真正的向量检索，实现 RAG 语义搜索
把生成的计划一键保存到今日计划或未来日期
增加 API Key 设置界面
增加联网失败时的友好提示
支持更多模型供应商
支持历史对话上下文
```

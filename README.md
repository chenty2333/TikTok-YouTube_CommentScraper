# 社交媒体评论抓取工具

这是一个用于抓取社交媒体平台视频评论的 Python 工具集。目前支持 TikTok 和 YouTube 两个平台的评论抓取。工具可以抓取主评论和回复，并将结果保存为 JSON 文件。该工具集具有增量保存功能，即使在中途中断也能保留已抓取的数据。

## 功能特点

- 支持抓取 TikTok 和 YouTube 视频评论
- 抓取主评论和回复评论
- 支持增量保存评论数据，防止意外中断导致数据丢失
- 可选择是否包含用户信息和评论时间
- 多种配置选项，适应不同场景
- 详细的日志输出，便于调试和监控
- 使用dotenv管理API密钥和Token

## 环境配置

### 系统要求

- Python 3.7+ 
- 操作系统：Windows, macOS, 或 Linux

### 安装依赖

#### 安装基础依赖
```bash
pip install python-dotenv
```

#### TikTok 爬虫依赖安装
```bash
pip install TikTokApi playwright asyncio
playwright install chromium
```

#### YouTube 爬虫依赖安装
```bash
pip install google-api-python-client requests
```

### 配置环境变量

本项目使用`.env`文件来管理API密钥和Token。请在项目根目录创建`.env`文件，并添加以下内容：

```
YOUTUBE_API_KEY=你的YouTube_API密钥
TIKTOK_MS_TOKEN=你的TikTok_MS_Token
```

配置好`.env`文件后，程序会自动从中读取密钥，无需手动设置环境变量。

## TikTok 评论抓取工具

### 基本用法

```bash
python tiktok_comments_scraper.py --url "https://www.tiktok.com/@username/video/1234567890123456789"
```

这将抓取指定视频的前 100 条评论及其回复，并保存到自动生成的 JSON 文件中。

### 命令行参数

| 参数 | 说明 | 默认值 |
| --- | --- | --- |
| `--url` | TikTok 视频 URL | 示例 URL |
| `--count` | 要抓取的评论数量 | 100 |
| `--output` | 输出文件名 | 自动生成 (tiktok_时间戳.json) |
| `--no-replies` | 不包含二级评论(回复) | False (默认包含回复) |
| `--include-user` | 包含用户信息 | False |
| `--include-time` | 包含评论时间 | False |
| `--debug` | 启用调试模式，输出更多信息 | False |
| `--show-browser` | 显示浏览器窗口 (不使用无头模式) | False |
| `--browser` | 使用的浏览器引擎 ("webkit" 或 "chromium") | "chromium" |
| `--no-ms-token` | 不使用 ms_token | False |

### TikTok 使用示例

1. 抓取指定视频的 200 条评论，包含二级回复：

```bash
python tiktok_comments_scraper.py --url "https://www.tiktok.com/@username/video/1234567890123456789" --count 200
```

2. 抓取评论并包含用户信息和时间：

```bash
python tiktok_comments_scraper.py --url "视频URL" --include-user --include-time
```

3. 不抓取回复，只抓取主评论：

```bash
python tiktok_comments_scraper.py --url "视频URL" --no-replies
```

4. 显示浏览器窗口，便于调试：

```bash
python tiktok_comments_scraper.py --url "视频URL" --show-browser --debug
```

### TikTok ms_token 配置

ms_token 是 TikTok 用于验证请求的一个令牌。您可以通过以下方式配置：

1. 在`.env`文件中设置 `TIKTOK_MS_TOKEN=你的ms_token值`
2. 从浏览器中获取自己的 ms_token (在登录 TikTok 后，从 Cookie 中获取)

## YouTube 评论抓取工具

### YouTube API 密钥配置

使用 YouTube 评论抓取工具需要 Google API 密钥。您可以在 [Google Cloud Console](https://console.cloud.google.com/) 创建一个项目并启用 YouTube Data API v3 来获取 API 密钥。

配置 API 密钥：
1. 在`.env`文件中设置 `YOUTUBE_API_KEY=你的API密钥`

### 基本用法

```bash
python youtube_comments_scraper.py --url "https://www.youtube.com/watch?v=VIDEO_ID"
```

### 命令行参数

| 参数 | 说明 | 默认值 |
| --- | --- | --- |
| `--url` | YouTube 视频 URL 或 ID | 必填 |
| `--count` | 要获取的评论数量 | 100 |
| `--output` | 输出文件名 | 自动生成 (youtube_视频ID_时间戳.json) |
| `--no-replies` | 不包含回复评论 | False (默认包含回复) |
| `--sort` | 评论排序方式 ("relevance" 或 "time") | "relevance" |
| `--debug` | 启用调试模式 | False |

### YouTube 使用示例

1. 抓取指定视频的 200 条评论，按时间排序：

```bash
python youtube_comments_scraper.py --url "https://www.youtube.com/watch?v=VIDEO_ID" --count 200 --sort time
```

2. 仅抓取主评论，不包括回复：

```bash
python youtube_comments_scraper.py --url "VIDEO_ID" --no-replies
```

3. 将结果保存到指定文件：

```bash
python youtube_comments_scraper.py --url "https://www.youtube.com/watch?v=VIDEO_ID" --output "my_youtube_comments.json"
```

## 输出文件格式

两种爬虫的输出都是 JSON 格式，结构如下：

```json
[
  {
    "text": "评论内容",
    "like_count": 点赞数,
    "platform": "tiktok或youtube"
    // 其他可能的字段 (user, create_time 等)
  },
  // 更多评论...
]
```

## 项目文件说明

- `tiktok_comments_scraper.py`: TikTok评论抓取工具
- `youtube_comments_scraper.py`: YouTube评论抓取工具
- `config.py`: 环境变量配置加载模块
- `.env`: 密钥和Token配置文件（需自行创建）

## 注意事项

1. 社交媒体平台可能会限制频繁的请求，程序已内置随机延迟以减轻这个问题
2. 抓取大量评论可能需要较长时间，请耐心等待
3. 对于 TikTok，如果遇到验证码或登录要求，可能需要使用 `--show-browser` 参数来手动处理
4. 该工具仅供学习和研究使用，请遵守各平台的使用条款和相关法律法规
5. YouTube API 有配额限制，请注意控制请求频率
6. **重要**: 不要将您的`.env`文件提交到版本控制系统（如Git）中，建议将`.env`添加到`.gitignore`中

## 常见问题

### TikTok 相关

#### Q: 程序报错 "无法创建会话"
A: 尝试使用 `--show-browser` 参数查看浏览器状态，可能需要手动处理验证码。

#### Q: 抓取速度很慢
A: 为了避免被 TikTok 限制，程序故意放慢了抓取速度。可以适当减少 `--count` 参数值。

#### Q: 如何获取 ms_token?
A: 登录 TikTok 网页版后，打开浏览器开发者工具，在 Application > Cookies 中找到 ms_token。

### YouTube 相关

#### Q: API 密钥无效或配额超限
A: 确保您的 API 密钥有效并且启用了 YouTube Data API v3。如果配额超限，可能需要等待 24 小时或创建新的 API 密钥。

#### Q: 无法获取某些视频的评论
A: 某些 YouTube 视频可能禁用了评论功能，或者视频设为私有。

#### Q: 环境变量未正确加载
A: 确保已经安装`python-dotenv`库，并且`.env`文件位于项目根目录且格式正确。

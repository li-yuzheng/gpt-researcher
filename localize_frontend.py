# -*- coding: utf-8 -*-
"""把 gpt-researcher 内置前端（index.html + scripts.js）界面文案换成中文。
只替换可见文案，不动 id / class / value / 事件 / 逻辑。
"""
import re
import shutil
import sys
from pathlib import Path

FE = Path(r"D:\gpt-researcher\frontend")
HTML = FE / "index.html"
JS = FE / "scripts.js"


def rx(s: str) -> str:
    """把空格序列当作 \\s+ 匹配，兼容源码里的换行缩进。"""
    # re.escape 在 3.7+ 会把空格转成 "\\ "，需连反斜杠一起换掉
    return re.escape(s).replace("\\ ", r"\s+")


HTML_MAP = [
    # ---------- head ----------
    ('<html lang="en">', '<html lang="zh-CN">', "all"),
    ("<title>GPT Researcher</title>", "<title>GPT 研究员 · AI 深度研究助手</title>", "1"),
    ('content="A research assistant powered by GPT-4"', 'content="基于大模型的 AI 深度研究助手"', "1"),
    # ---------- 顶部导航 ----------
    ('<i class="fas fa-network-wired"></i> Status', '<i class="fas fa-network-wired"></i> 连接状态', "1"),
    ('<i class="fas fa-history"></i> History', '<i class="fas fa-history"></i> 历史记录', "1"),
    # ---------- 连接状态面板 ----------
    ('<i class="fas fa-plug"></i> Connection Status', '<i class="fas fa-plug"></i> 连接状态', "1"),
    ('title="Close panel"', 'title="关闭面板"', "all"),
    (">Connection:</span>", ">连接：</span>", "1"),
    ('id="connectionStatus">Disconnected<', 'id="connectionStatus">未连接<', "1"),
    (">Research:</span>", ">研究状态：</span>", "1"),
    ('id="researchStatus">Inactive<', 'id="researchStatus">未启动<', "1"),
    (">Connected for:</span>", ">已连接时长：</span>", "1"),
    (">Last activity:</span>", ">最近活动：</span>", "1"),
    (">ReadyState:</span>", ">就绪状态码：</span>", "1"),
    (">Connection attempts:</span>", ">连接尝试次数：</span>", "1"),
    (">Messages received:</span>", ">已收消息数：</span>", "1"),
    (">Current task:</span>", ">当前任务：</span>", "1"),
    # ---------- 首屏 ----------
    ("Say Goodbye to <br>", "告别<br>", "1"),
    ("Hours of Research</span>", "数小时的资料搜集</span>", "1"),
    (
        "Say Hello to <b>GPT Researcher</b>, your AI mate for rapid insights and comprehensive research. <br>"
        " GPT Researcher takes care of everything from accurate source gathering and organization of research"
        " results to generation of customized reports with citations.",
        "欢迎使用 <b>GPT 研究员</b>——你的 AI 研究伙伴，帮你快速获得洞察、完成全面调研。<br>"
        " 从精准采集信息源、梳理研究结论，到生成带引用的定制化报告，全流程自动完成。",
        "1",
    ),
    (">Start Researching</a>", ">开始研究</a>", "1"),
    # ---------- 表单 ----------
    ('alt="Auto Agent"', 'alt="自动研究代理"', "1"),
    ("What would you like me to research next?", "你想让我研究什么课题？", "1"),
    ('placeholder="Enter any topic, question, or idea..."', 'placeholder="输入任意主题、问题或想法……"', "1"),
    (">Auto Agent</button>", ">自动研究代理</button>", "1"),
    (
        "What type of report would you like me to generate?",
        "你想要哪种类型的报告？",
        "1",
    ),
    ('value="research_report">Summary - Short and fast (~2 min)', 'value="research_report">概要报告 · 简洁快速（约 2 分钟）', "1"),
    ('value="detailed_report">Detailed - In depth and longer (~5 min)', 'value="detailed_report">深度报告 · 详实深入（约 5 分钟）', "1"),
    ('value="resource_report">Resource Report', 'value="resource_report">资源清单报告', "1"),
    ('value="deep">Deep Research', 'value="deep">深度研究 · 多轮递归', "1"),
    (
        "In which tone would you like the report to be generated?",
        "你希望报告使用哪种语气？",
        "1",
    ),
    ("Objective - Impartial and unbiased presentation of facts and findings", "客观 · 中立呈现事实与发现", "1"),
    ("Formal - Adheres to academic standards with sophisticated language and structure", "正式 · 符合学术规范，语言与结构严谨", "1"),
    ("Analytical - Critical evaluation and detailed examination of data and theories", "分析 · 批判性评估，深入考察数据与理论", "1"),
    ("Persuasive - Convincing the audience of a particular viewpoint or argument", "说服 · 用论据引导读者接受特定观点", "1"),
    ("Informative - Providing clear and comprehensive information on a topic", "信息型 · 清晰全面地介绍主题", "1"),
    ("Explanatory - Clarifying complex concepts and processes", "解释型 · 阐明复杂概念与流程", "1"),
    ("Descriptive - Detailed depiction of phenomena, experiments, or case studies", "描述型 · 细致刻画现象、实验或案例", "1"),
    ("Critical - Judging the validity and relevance of the research and its conclusions", "批判型 · 评判研究结论的有效性与相关性", "1"),
    (
        "Comparative - Juxtaposing different theories, data, or methods to highlight differences and similarities",
        "比较型 · 并列不同理论、数据或方法，突出异同",
        "1",
    ),
    (
        "Speculative - Exploring hypotheses and potential implications or future research directions",
        "推测型 · 探讨假设、潜在影响与未来研究方向",
        "1",
    ),
    ("Reflective - Considering the research process and personal insights or experiences", "反思型 · 回顾研究过程与个人洞察", "1"),
    ("Narrative - Telling a story to illustrate research findings or methodologies", "叙事型 · 用讲故事的方式呈现研究发现", "1"),
    ("Humorous - Light-hearted and engaging, usually to make the content more relatable", "幽默型 · 轻松活泼，增强可读性", "1"),
    ("Optimistic - Highlighting positive findings and potential benefits", "乐观型 · 突出积极发现与潜在收益", "1"),
    ("Pessimistic - Focusing on limitations, challenges, or negative outcomes", "审慎型 · 聚焦局限、挑战与不利结果", "1"),
    (
        "What sources would you like me to research from?",
        "你希望从哪些来源开展研究？",
        "1",
    ),
    (
        "You can now do research on local documents as well. Please make sure to add the DOC_PATH env"
        " variable pointing to your documents folder.",
        "现在也支持研究本地文档。请确保已设置环境变量 DOC_PATH 指向你的文档目录。",
        "1",
    ),
    ('value="web">The Web', 'value="web">网络搜索', "1"),
    ('value="local">My Documents', 'value="local">我的本地文档', "1"),
    ('value="hybrid">Hybrid', 'value="hybrid">混合（网络 + 本地）', "1"),
    ('value="azure">Azure storage', 'value="azure">Azure 存储', "1"),
    ("How many websites should be scraped per query?", "每次搜索抓取多少个网页？", "1"),
    ("Controls the number of websites scraped per search query (default: 5)", "控制每个搜索词抓取的网页数量（默认 5）", "1"),
    ('for="queryDomains" class="form-label">Query Domains (Optional)', 'for="queryDomains" class="form-label">限定搜索域名（可选）', "1"),
    ('placeholder="Enter domains separated by commas"', 'placeholder="输入域名，用英文逗号分隔"', "1"),
    ("Example: techcrunch.com, forbes.com", "例如：techcrunch.com, forbes.com", "1"),
    # ---------- MCP ----------
    ("Enable MCP (Model Context Protocol)", "启用 MCP（模型上下文协议）", "1"),
    ('title="Learn about MCP"', 'title="了解 MCP"', "1"),
    ("Connect to external tools and data sources through MCP servers", "通过 MCP 服务器接入外部工具与数据源", "1"),
    (">Quick Presets", ">快捷预设", "1"),
    ("Tavily Web Search", "Tavily 网页搜索", "1"),
    ("Local Files", "本地文件", "1"),
    ("Click a preset to add pre-configured MCP servers to the JSON below", "点击预设，把服务器配置自动填入下方 JSON", "1"),
    ("MCP Servers Configuration", "MCP 服务器配置", "1"),
    ('placeholder="Paste your MCP servers configuration as JSON array..."', 'placeholder="粘贴 MCP 服务器配置（JSON 数组）……"', "1"),
    (">Valid JSON ✓<", ">JSON 格式正确 ✓<", "1"),
    ("Format JSON", "格式化 JSON", "1"),
    (
        "Paste your MCP servers configuration as a JSON array. Each server should have properties like"
        ' <code>name</code>, <code>command</code>, <code>args</code>, and optional <code>env</code> variables.',
        "以 JSON 数组形式粘贴 MCP 服务器配置。每个服务器需包含 <code>name</code>、<code>command</code>、"
        "<code>args</code> 等字段，可选 <code>env</code> 环境变量。",
        "1",
    ),
    ("See example →", "查看示例 →", "1"),
    ('value="Begin Research"', 'value="开始研究"', "1"),
    # ---------- 进度 / 报告 ----------
    ("Research Progress", "研究进度", "1"),
    ("Watch as the AI works to gather information and analyze your topic in real-time.", "实时查看 AI 搜集信息、分析课题的完整过程。", "1"),
    ("title=\"Expand\"", "title=\"展开\"", "all"),
    (">Research Report", ">研究报告", "1"),
    ('title="Copy"', 'title="复制"', "1"),
    # ---------- 对话 ----------
    ("Chat with AI about this research", "围绕这份报告继续追问", "1"),
    ("Ask questions about the research report to get more insights", "针对这份报告提问，挖掘更多细节", "1"),
    ('placeholder="Ask a question about this research..."', 'placeholder="输入你想追问的问题……"', "1"),
    ('title="Use voice input"', 'title="语音输入"', "1"),
    ("</i> Send", "</i> 发送", "1"),
    # ---------- 历史面板 ----------
    ("Research History", "研究历史", "1"),
    ('placeholder="Search research history..."', 'placeholder="搜索历史记录……"', "1"),
    ('title="Search"', 'title="搜索"', "1"),
    ('value="newest">Newest First', 'value="newest">最新优先', "1"),
    ('value="oldest">Oldest First', 'value="oldest">最早优先', "1"),
    ('title="Clear all history"', 'title="清空全部历史"', "1"),
    # ---------- 底部下载条 ----------
    ("Copy (Markdown)", "复制（Markdown）", "1"),
    ("Log (JSON)", "日志（JSON）", "1"),
    # ---------- 页脚 ----------
    (">Homepage</a>", ">官网</a>", "1"),
    ("GPT Researcher &copy; 2024", "GPT 研究员 &copy; 2024", "1"),
]

JS_MAP = [
    # WebSocket 状态
    ("statusText: 'Disconnected'", "statusText: '未连接'", "all"),
    ("statusText: 'Connecting'", "statusText: '连接中'", "1"),
    ("statusText: 'Connected'", "statusText: '已连接'", "1"),
    ("statusText: 'Closing'", "statusText: '关闭中'", "1"),
    ("return '0 (Connecting)'", "return '0（连接中）'", "1"),
    ("return '1 (Open)'", "return '1（已打开）'", "1"),
    ("return '2 (Closing)'", "return '2（关闭中）'", "1"),
    ("return '3 (Closed)'", "return '3（已关闭）'", "1"),
    ("return `${readyState} (Unknown)`", "return `${readyState}（未知）`", "1"),
    # 时长格式
    ("return `${seconds} sec`", "return `${seconds} 秒`", "1"),
    ("return `${Math.floor(seconds / 60)} min ${seconds % 60} sec`", "return `${Math.floor(seconds / 60)} 分 ${seconds % 60} 秒`", "1"),
    ("return `${hours} hr ${minutes} min`", "return `${hours} 小时 ${minutes} 分`", "1"),
    ("`${elapsed} sec ago`", "`${elapsed} 秒前`", "1"),
    ("formatDuration(elapsed) + ' ago'", "formatDuration(elapsed) + '前'", "1"),
    ("isResearchActive ? 'Active' : 'Inactive'", "isResearchActive ? '研究中' : '未启动'", "1"),
    # 历史面板
    ('<p class="text-center mt-4 text-muted">No research history yet.</p>', '<p class="text-center mt-4 text-muted">暂无研究历史</p>', "1"),
    ("'Unnamed Research'", "'未命名研究'", "1"),
    ('title="Open PDF Report"', 'title="打开 PDF 报告"', "1"),
    ('title="Open Word Document"', 'title="打开 Word 文档"', "1"),
    ('title="Open Markdown File"', 'title="打开 Markdown 文件"', "1"),
    ('title="Open JSON Data"', 'title="打开 JSON 数据"', "1"),
    ('title="Delete this research entry"', 'title="删除这条研究记录"', "1"),
    ("'Are you sure you want to delete this research entry?'", "'确定要删除这条研究记录吗？'", "1"),
    ("'Are you sure you want to clear all research history? This cannot be undone.'", "'确定要清空全部研究历史吗？此操作不可恢复。'", "1"),
    ("'Research history saved!'", "'研究历史已保存！'", "1"),
    ("'Error saving history. Some entries may not be saved.'", "'保存历史时出错，部分记录可能未保存。'", "1"),
    ("'Entry deleted successfully'", "'已删除该记录'", "1"),
    ("'Research history cleared successfully'", "'研究历史已清空'", "1"),
    ("'Research parameters loaded. You can start the research again.'", "'研究参数已载入，可以重新开始研究。'", "1"),
    ("'Research content copied to clipboard!'", "'研究内容已复制到剪贴板！'", "1"),
    ("'No download links provided'", "'暂无下载链接'", "1"),
    ("'Error: Could not save research to history'", "'错误：无法把本次研究写入历史'", "1"),
    ("'Research saved! Your history is stored in a browser cookie.'", "'研究已保存！历史记录存放在浏览器 Cookie 中。'", "1"),
    ("'Research saved! Your history is stored using localStorage.'", "'研究已保存！历史记录存放在 localStorage 中。'", "1"),
    ('"Cookies are disabled. History will use localStorage instead."', '"浏览器已禁用 Cookie，历史记录将改用 localStorage 存储。"', "1"),
    # 进度文案
    ("'🧙‍♂️ Gathering information and analyzing your research topic...'", "'🧙‍♂️ 正在搜集资料并分析你的研究主题……'", "1"),
    ("'🤔 Pondering your question from several angles'", "'🤔 正在从多个角度思考你的问题'", "1"),
    ("'No output data received'", "'未收到输出数据'", "1"),
    ("'Copied to clipboard!'", "'已复制到剪贴板！'", "1"),
    ("status = 'Research in progress...'", "status = '研究进行中……'", "1"),
    ("status = 'Research finished!'", "status = '研究完成！'", "1"),
    ("status = 'Research failed!'", "status = '研究失败！'", "1"),
    ("'<i class=\"fas fa-copy\"></i> Copy'", "'<i class=\"fas fa-copy\"></i> 复制'", "1"),
    ("</i> Copied!'", "</i> 已复制！'", "1"),
    # 图片查看
    ("img.alt = 'Full-size Research Image'", "img.alt = '查看大图'", "1"),
    ("'Research Image'", "'研究配图'", "1"),
    ("closeBtn.textContent = 'Close'", "closeBtn.textContent = '关闭'", "1"),
    # 聊天
    ("'I can answer questions about the research report. What would you like to know?'", "'我可以围绕这份研究报告回答你的问题，你想了解什么？'", "1"),
    ("'Speech recognition not supported in this browser'", "'当前浏览器不支持语音识别'", "1"),
    ("'Microphone access denied. Please allow microphone access in your browser settings.'", "'麦克风权限被拒绝，请在浏览器设置中允许访问麦克风。'", "1"),
    ("button.title = 'Stop listening'", "button.title = '停止录音'", "1"),
    ("button.title = 'Use voice input'", "button.title = '语音输入'", "1"),
    ("'Unable to send message. Connection is unavailable.'", "'无法发送消息，连接不可用。'", "1"),
    # 面板标题
    ("button.title = 'Collapse'", "button.title = '折叠'", "1"),
    ("button.title = 'Expand'", "button.title = '展开'", "1"),
    ("exportBtn.title = 'Export research history to file'", "exportBtn.title = '导出研究历史到文件'", "1"),
    ("importBtn.title = 'Import research history from file'", "importBtn.title = '从文件导入研究历史'", "1"),
    ("debugBtn.title = 'Check storage status'", "debugBtn.title = '检查存储状态'", "1"),
    # MCP
    ("mcpConfigStatus.textContent = 'Empty configuration'", "mcpConfigStatus.textContent = '配置为空'", "1"),
    (
        "mcpConfigStatus.textContent = `Valid JSON ✓ (${parsed.length} server${parsed.length !== 1 ? 's' : ''})`",
        "mcpConfigStatus.textContent = `JSON 格式正确 ✓（${parsed.length} 个服务器）`",
        "1",
    ),
    ("mcpConfigStatus.textContent = `Invalid JSON: ${error.message}`", "mcpConfigStatus.textContent = `JSON 格式错误：${error.message}`", "1"),
    ("'JSON formatted successfully!'", "'JSON 格式化完成！'", "1"),
    ("'Cannot format invalid JSON'", "'JSON 无效，无法格式化'", "1"),
    ("'Example configuration loaded!'", "'已载入示例配置！'", "1"),
    ("'MCP enabled - will be included in research process'", "'MCP 已启用，将参与研究流程'", "1"),
    ("'MCP disabled - using web search only'", "'MCP 已关闭，仅使用网页搜索'", "1"),
    # 导入导出
    ("'Import functionality not available'", "'导入功能不可用'", "1"),
    ("'Imported data is not an array'", "'导入的数据不是数组格式'", "1"),
    ("'No valid research entries found in the imported file'", "'导入文件中没有有效的研究记录'", "1"),
    ("'Error importing research history: Invalid file format'", "'导入研究历史失败：文件格式无效'", "1"),
    ("'Error reading the imported file'", "'读取导入文件失败'", "1"),
    ("'No research history to export'", "'没有可导出的研究历史'", "1"),
    ("'Research history exported to JSON file'", "'研究历史已导出为 JSON 文件'", "1"),
    ("'Error exporting research history'", "'导出研究历史失败'", "1"),
]


def apply_map(text: str, mapping, label: str):
    ok, miss = 0, []
    for old, new, mode in mapping:
        cnt = 0 if mode == "all" else 1
        new_text, n = re.subn(rx(old), lambda m: new, text, count=cnt)
        if n == 0:
            miss.append(old[:60])
        else:
            text = new_text
            ok += n
    print(f"  {label}: 命中 {ok} 处，未命中 {len(miss)} 条")
    for m in miss:
        print(f"    [未命中] {m}")
    return text


def main():
    for p in (HTML, JS):
        bak = p.with_suffix(p.suffix + ".bak")
        if not bak.exists():
            shutil.copy2(p, bak)
            print(f"备份: {bak.name}")

    h = HTML.read_text(encoding="utf-8")
    j = JS.read_text(encoding="utf-8")
    print("应用替换：")
    h = apply_map(h, HTML_MAP, "index.html")
    j = apply_map(j, JS_MAP, "scripts.js")
    HTML.write_text(h, encoding="utf-8")
    JS.write_text(j, encoding="utf-8")

    def zh(t):
        return len(re.findall(r"[\u4e00-\u9fff]", t))

    print(f"\n中文字符数: index.html {zh(h)} | scripts.js {zh(j)}")
    # JS 语法自检：括号配平 + 反引号成对
    for name, t in (("index.html", h), ("scripts.js", j)):
        bt = t.count("`")
        print(f"  {name}: 反引号 {bt} 个 ({'配对' if bt % 2 == 0 else '不配对!'})")
    for ch_open, ch_close in (("{", "}"), ("(", ")"), ("[", "]")):
        d = j.count(ch_open) - j.count(ch_close)
        print(f"  scripts.js {ch_open}{ch_close} 差值: {d}")


if __name__ == "__main__":
    sys.exit(main())

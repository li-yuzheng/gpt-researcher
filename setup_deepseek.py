# -*- coding: utf-8 -*-
"""
gpt-researcher -> DeepSeek 一键改造脚本
=========================================

用法：
    1. 把本文件复制到 gpt-researcher 项目根目录（与 main.py 同级）
    2. 在 PyCharm 里右键 Run，或终端执行：
           python setup_deepseek.py

它会做 5 件事（每步都有 .bak 备份，可重复执行不会重复改）：
    [1] 生成 .env（若已存在则生成 .env.deepseek.template，绝不覆盖你的配置）
    [2] gpt_researcher/config/variables/default.py  默认模型改成 deepseek
    [3] gpt_researcher/llm_provider/generic/base.py  温度黑名单 + base_url 可覆盖
    [4] gpt_researcher/memory/embeddings.py          custom 分支独立 key/base
    [5] backend/server/app.py                        PDF 导出失败不再拖垮整个请求

改完用 ast 做语法校验，全部通过才算成功。
"""

from __future__ import annotations

import ast
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent

FILES = {
    "default": ROOT / "gpt_researcher" / "config" / "variables" / "default.py",
    "base": ROOT / "gpt_researcher" / "llm_provider" / "generic" / "base.py",
    "embeddings": ROOT / "gpt_researcher" / "memory" / "embeddings.py",
    "app": ROOT / "backend" / "server" / "app.py",
}

ENV_TEMPLATE = """# ===== DeepSeek 对话模型 =====
DEEPSEEK_API_KEY=sk-在这里填你的DeepSeek密钥
DEEPSEEK_BASE_URL=https://api.deepseek.com

FAST_LLM=deepseek:deepseek-chat
SMART_LLM=deepseek:deepseek-chat
STRATEGIC_LLM=deepseek:deepseek-chat

# 想用推理模型就换成下面这行（更慢，但质量更好）
# SMART_LLM=deepseek:deepseek-reasoner

# ===== 嵌入模型（DeepSeek 不提供 embedding 接口，这里用硅基流动）=====
# 换成本地 ollama 就写： EMBEDDING=ollama:bge-m3 / OLLAMA_BASE_URL=http://localhost:11434
EMBEDDING=custom:BAAI/bge-m3
CUSTOM_EMBEDDING_BASE_URL=https://api.siliconflow.cn/v1
CUSTOM_EMBEDDING_API_KEY=sk-在这里填你的硅基流动密钥

# ===== 联网搜索（必需）=====
TAVILY_API_KEY=tvly-在这里填你的Tavily密钥

# ===== 报告参数 =====
LANGUAGE=chinese
TOTAL_WORDS=1500
MAX_ITERATIONS=3
TEMPERATURE=0.4
DOC_PATH=./my-docs
"""


def log(msg: str = "") -> None:
    print(msg, flush=True)


def fail(msg: str) -> None:
    log("\n[ERROR] " + msg)
    sys.exit(1)


def backup(path: Path) -> None:
    bak = path.with_suffix(path.suffix + ".bak")
    if not bak.exists():
        shutil.copy2(path, bak)


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def write(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")


# ---------------------------------------------------------------- [0] 环境校验
def check_project() -> None:
    if not (ROOT / "main.py").exists() or not (ROOT / "gpt_researcher").is_dir():
        fail(
            "当前目录不像 gpt-researcher 项目根目录。\n"
            f"  当前目录: {ROOT}\n"
            "  请把本脚本放到能看到 main.py 和 gpt_researcher 文件夹的那一层。"
        )
    missing = [str(p.relative_to(ROOT)) for p in FILES.values() if not p.exists()]
    if missing:
        fail("以下文件不存在，可能仓库版本有差异：\n  - " + "\n  - ".join(missing))


# ---------------------------------------------------------------- [1] .env
def step_env() -> None:
    env = ROOT / ".env"
    if env.exists():
        if "DEEPSEEK_API_KEY" in read(env):
            log("[1/5] .env 已存在且已含 DeepSeek 配置，跳过。")
            return
        tpl = ROOT / ".env.deepseek.template"
        write(tpl, ENV_TEMPLATE)
        log(f"[1/5] .env 已存在，未覆盖。已生成 {tpl.name}，请手动合并其中的键。")
        return
    write(env, ENV_TEMPLATE)
    log("[1/5] 已生成 .env（记得把 sk-xxx 占位符换成真实密钥）")


# ---------------------------------------------------------------- [2] default.py
def step_default() -> None:
    path = FILES["default"]
    text = read(path)
    original = text

    targets = {
        "EMBEDDING": "custom:BAAI/bge-m3",
        "FAST_LLM": "deepseek:deepseek-chat",
        "SMART_LLM": "deepseek:deepseek-chat",
        "STRATEGIC_LLM": "deepseek:deepseek-chat",
        "LANGUAGE": "chinese",
    }
    changed = []
    for key, value in targets.items():
        pattern = re.compile(r'("' + key + r'":\s*)"[^"]*"')
        text, n = pattern.subn(lambda m, v=value: m.group(1) + '"' + v + '"', text, count=1)
        if n:
            changed.append(key)

    if text == original:
        log("[2/5] default.py 无需修改（可能已改过）。")
        return
    backup(path)
    write(path, text)
    log(f"[2/5] default.py 已改: {', '.join(changed)}")


# ---------------------------------------------------------------- [3] base.py
# 注意：块的缩进沿用原文（正则从 elif/case 关键字开始匹配，前导空格不在匹配内），
# 所以首行不能带缩进，后续行必须带缩进。
BASE_DEEPSEEK_BLOCK = '''elif provider == "deepseek":
            _check_pkg("langchain_openai")
            from langchain_openai import ChatOpenAI

            # 支持 DEEPSEEK_BASE_URL 覆盖，方便走中转站/代理
            llm = ChatOpenAI(
                openai_api_base=os.environ.get(
                    "DEEPSEEK_BASE_URL", "https://api.deepseek.com"
                ),
                openai_api_key=os.environ["DEEPSEEK_API_KEY"],
                **kwargs
            )'''

BASE_NO_TEMP_ANCHOR = '    "deepseek/deepseek-reasoner",\n'


def step_base() -> None:
    path = FILES["base"]
    text = read(path)
    original = text
    notes = []

    # (a) 温度黑名单补 "deepseek-reasoner"
    if '"deepseek-reasoner",' not in text:
        if BASE_NO_TEMP_ANCHOR not in text:
            fail('base.py 里没找到 "deepseek/deepseek-reasoner"，请检查仓库版本。')
        text = text.replace(
            BASE_NO_TEMP_ANCHOR,
            BASE_NO_TEMP_ANCHOR + '    "deepseek-reasoner",  # 官方接口的模型名不带前缀\n',
            1,
        )
        notes.append("温度黑名单 +deepseek-reasoner")

    # (b) deepseek 分支支持自定义 base_url
    if "DEEPSEEK_BASE_URL" not in text:
        pattern = re.compile(
            r'elif provider == "deepseek":\n.*?(?=\n( *)elif provider == "litellm":)',
            re.S,
        )
        text, n = pattern.subn(lambda m: BASE_DEEPSEEK_BLOCK, text, count=1)
        if not n:
            fail('没能定位 base.py 的 deepseek 分支（找不到后一个 elif provider == "litellm":）。')
        notes.append("base_url 可覆盖")

    if text == original:
        log("[3/5] base.py 无需修改（可能已改过）。")
        return
    backup(path)
    write(path, text)
    log(f"[3/5] base.py 已改: {' / '.join(notes)}")


# ---------------------------------------------------------------- [4] embeddings.py
EMB_CUSTOM_BLOCK = '''case "custom":
                from langchain_openai import OpenAIEmbeddings

                # 独立配置，避免与 OPENAI_* 混用（DeepSeek 没有 embedding 接口）
                _embeddings = OpenAIEmbeddings(
                    model=model,
                    openai_api_key=os.getenv(
                        "CUSTOM_EMBEDDING_API_KEY",
                        os.getenv("OPENAI_API_KEY", "custom"),
                    ),
                    openai_api_base=os.getenv(
                        "CUSTOM_EMBEDDING_BASE_URL",
                        os.getenv("OPENAI_BASE_URL", "http://localhost:1234/v1"),
                    ),
                    check_embedding_ctx_length=False,
                    **embedding_kwargs,
                )  # quick fix for lmstudio'''


def step_embeddings() -> None:
    path = FILES["embeddings"]
    text = read(path)
    if "CUSTOM_EMBEDDING_API_KEY" in text:
        log("[4/5] embeddings.py 无需修改（可能已改过）。")
        return

    pattern = re.compile(r'case "custom":\n.*?(?=\n( *)case "openai":)', re.S)
    new_text, n = pattern.subn(lambda m: EMB_CUSTOM_BLOCK, text, count=1)
    if not n:
        fail('没能定位 embeddings.py 的 case "custom": 分支。')
    backup(path)
    write(path, new_text)
    log("[4/5] embeddings.py 已改: custom 分支改用 CUSTOM_EMBEDDING_API_KEY / _BASE_URL")


# ---------------------------------------------------------------- [5] app.py
def step_pdf() -> None:
    path = FILES["app"]
    text = read(path)
    if "PDF 生成失败" in text:
        log("[5/5] app.py 无需修改（可能已改过）。")
        return

    old = "    pdf_path = await write_md_to_pdf(report_information[0], research_id)"
    if old not in text:
        log("[5/5] app.py 未找到 write_md_to_pdf 调用，跳过（不影响主流程）。")
        return

    new = (
        "    try:\n"
        "        pdf_path = await write_md_to_pdf(report_information[0], research_id)\n"
        "    except Exception as e:\n"
        '        logger.warning(f"PDF 生成失败，已跳过（不影响 Markdown/Word 导出）: {e}")\n'
        "        pdf_path = None"
    )
    backup(path)
    write(path, text.replace(old, new, 1))
    log("[5/5] app.py 已改: PDF 导出失败不再中断请求")


# ---------------------------------------------------------------- 语法校验
def verify() -> None:
    log("\n--- 语法校验 ---")
    bad = []
    for path in FILES.values():
        rel = path.relative_to(ROOT)
        try:
            ast.parse(read(path), filename=str(path))
            log(f"  [OK]   {rel}")
        except SyntaxError as e:
            bad.append(f"{rel}: 第 {e.lineno} 行 {e.msg}")
            log(f"  [FAIL] {rel} -> 第 {e.lineno} 行 {e.msg}")
    if bad:
        log("\n改动后存在语法错误，请用同目录的 *.bak 回滚：")
        for line in bad:
            log("  - " + line)
        sys.exit(1)
    log("\n全部通过。")


def main() -> None:
    log("gpt-researcher -> DeepSeek 改造")
    log("=" * 40)
    check_project()
    step_env()
    step_default()
    step_base()
    step_embeddings()
    step_pdf()
    verify()

    log(
        "\n下一步：\n"
        "  1. 打开 .env，把 sk-xxx / tvly-xxx 占位符换成真实密钥\n"
        "  2. 运行验证脚本确认对话链路（见 guide 第七章）\n"
        "  3. 运行 main.py，浏览器打开 http://localhost:8000\n"
        "\n回滚：把同目录下的 *.bak 改回原文件名即可。"
    )


if __name__ == "__main__":
    main()

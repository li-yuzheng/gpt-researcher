import aiofiles
import urllib
import mistune
import os
import re
import shutil
import subprocess
import sys
import tempfile

async def write_to_file(filename: str, text: str) -> None:
    """Asynchronously write text to a file in UTF-8 encoding.

    Args:
        filename (str): The filename to write to.
        text (str): The text to write.
    """
    # Ensure text is a string
    if not isinstance(text, str):
        text = str(text)

    # Convert text to UTF-8, replacing any problematic characters
    text_utf8 = text.encode('utf-8', errors='replace').decode('utf-8')

    async with aiofiles.open(filename, "w", encoding='utf-8') as file:
        await file.write(text_utf8)

async def write_text_to_md(text: str, filename: str = "") -> str:
    """Writes text to a Markdown file and returns the file path.

    Args:
        text (str): Text to write to the Markdown file.

    Returns:
        str: The file path of the generated Markdown file.
    """
    import uuid

    safe_name = (filename or "").strip()[:60] or f"report-{uuid.uuid4().hex[:12]}"
    safe_name = safe_name.replace("/", "-").replace("\\", "-")
    os.makedirs("outputs", exist_ok=True)
    file_path = f"outputs/{safe_name}.md"
    await write_to_file(file_path, text)
    return urllib.parse.quote(file_path)

def _preprocess_images_for_pdf(text: str) -> str:
    """Convert web image URLs to absolute file paths for PDF generation.
    
    Transforms /outputs/images/... URLs to absolute file:// paths that
    weasyprint can resolve.
    """
    import re
    
    base_path = os.path.abspath(".")
    
    # Pattern to find markdown images with /outputs/ URLs
    def replace_image_url(match):
        alt_text = match.group(1)
        url = match.group(2)
        
        # Convert /outputs/... to absolute path
        if url.startswith("/outputs/"):
            abs_path = os.path.join(base_path, url.lstrip("/"))
            return f"![{alt_text}]({abs_path})"
        return match.group(0)
    
    # Match ![alt text](/outputs/images/...)
    pattern = r'!\[([^\]]*)\]\((/outputs/[^)]+)\)'
    return re.sub(pattern, replace_image_url, text)


# 打印专用补充样式：覆盖 pdf_styles.css 的中文字体、@page 与表格分页规则
_PDF_PRINT_CSS = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "styles", "pdf_print.css"
)


def _find_pdf_browser() -> str:
    """定位可用于把 HTML 打印成 PDF 的 Chromium 系浏览器。

    Edge / Chrome 自带完整的 HTML+CSS 渲染引擎与中文字体，在 Windows 上
    不需要 GTK（weasyprint 的硬依赖），macOS / Linux 上通常也已安装。
    """
    candidates = []

    if sys.platform == "win32":
        roots = [
            os.environ.get("PROGRAMFILES"),
            os.environ.get("PROGRAMFILES(X86)"),
            os.environ.get("LOCALAPPDATA"),
        ]
        relatives = [
            os.path.join("Microsoft", "Edge", "Application", "msedge.exe"),
            os.path.join("Google", "Chrome", "Application", "chrome.exe"),
        ]
        for root in roots:
            if root:
                candidates.extend(os.path.join(root, rel) for rel in relatives)
    elif sys.platform == "darwin":
        candidates.extend([
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
            "/Applications/Chromium.app/Contents/MacOS/Chromium",
        ])
    else:
        for name in ("google-chrome", "chromium", "chromium-browser",
                     "microsoft-edge", "microsoft-edge-stable"):
            found = shutil.which(name)
            if found:
                candidates.append(found)

    for path in candidates:
        if path and os.path.isfile(path):
            return path
    return ""


def _read_css(*paths: str) -> str:
    """按顺序拼接多个 css 文件，后加载的覆盖先加载的。"""
    chunks = []
    for path in paths:
        if path and os.path.isfile(path):
            with open(path, "r", encoding="utf-8") as fh:
                chunks.append(fh.read())
    return "\n".join(chunks)


def _absolutize_image_src(html: str) -> str:
    """把 <img src> 中的本地路径转成 file:// URL，浏览器才能加载。"""
    def _replace(match):
        src = match.group(1)
        if src.startswith(("http://", "https://", "data:", "file://")):
            return match.group(0)
        normalized = src.replace("\\", "/")
        if re.match(r"^[A-Za-z]:/", normalized):
            return 'src="file:///%s"' % normalized
        if normalized.startswith("/outputs/"):
            absolute = os.path.abspath(normalized.lstrip("/")).replace("\\", "/")
            return 'src="file:///%s"' % absolute
        if normalized.startswith("/"):
            return 'src="file://%s"' % normalized
        return match.group(0)

    return re.sub(r'src="([^"]+)"', _replace, html)


def _build_print_html(text: str, css_path: str) -> str:
    """把报告 Markdown 渲染成一份自带样式的独立 HTML。"""
    markdown = mistune.create_markdown(escape=False, plugins=["table", "strikethrough"])
    body = _absolutize_image_src(markdown(text))
    css = _read_css(css_path, _PDF_PRINT_CSS)
    return (
        '<!DOCTYPE html>\n<html lang="zh-CN">\n<head>\n<meta charset="utf-8">\n'
        '<title>report</title>\n<style>\n' + css + '\n</style>\n</head>\n<body>\n'
        + body + '\n</body>\n</html>\n'
    )


def _html_to_pdf_via_browser(text: str, css_path: str, pdf_path: str) -> bool:
    """用系统浏览器无头模式把报告打印成 PDF，成功返回 True。"""
    browser = _find_pdf_browser()
    if not browser:
        return False

    pdf_abs = os.path.abspath(pdf_path)
    workdir = tempfile.mkdtemp(prefix="gptr-pdf-")
    html_path = os.path.join(workdir, "report.html")
    profile_dir = os.path.join(workdir, "profile")

    try:
        with open(html_path, "w", encoding="utf-8") as fh:
            fh.write(_build_print_html(text, css_path))

        url = "file:///" + os.path.abspath(html_path).replace("\\", "/")

        # 不同 Chromium 版本对参数的支持不同，逐组降级尝试
        flag_sets = (
            ("--headless=new", "--no-pdf-header-footer"),
            ("--headless=new", "--print-to-pdf-no-header"),
            ("--headless", "--no-pdf-header-footer"),
            ("--headless", "--print-to-pdf-no-header"),
        )
        for flags in flag_sets:
            if os.path.exists(pdf_abs):
                os.remove(pdf_abs)
            args = [
                browser, *flags,
                "--disable-gpu",
                "--no-first-run",
                "--no-default-browser-check",
                "--disable-extensions",
                "--disable-background-networking",
                "--disable-sync",
                "--virtual-time-budget=8000",
                f"--user-data-dir={profile_dir}",
                f"--print-to-pdf={pdf_abs}",
                url,
            ]
            try:
                subprocess.run(args, capture_output=True, timeout=90)
            except Exception:
                continue
            if os.path.isfile(pdf_abs) and os.path.getsize(pdf_abs) > 1024:
                return True
        return False
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


async def write_md_to_pdf(text: str, filename: str = "") -> str:
    """Converts Markdown text to a PDF file and returns the file path.

    Args:
        text (str): Markdown text to convert.

    Returns:
        str: The encoded file path of the generated PDF.
    """
    import uuid

    # Empty / whitespace-only filename previously wrote "outputs/.pdf" which
    # confuses download UIs (#1718). Prefer a stable non-empty basename.
    safe_name = (filename or "").strip()[:60] or f"report-{uuid.uuid4().hex[:12]}"
    # Replace path separators to keep the PDF under outputs/.
    safe_name = safe_name.replace("/", "-").replace("\\", "-")
    os.makedirs("outputs", exist_ok=True)
    file_path = f"outputs/{safe_name}.pdf"

    try:
        # Resolve css path relative to this backend module to avoid
        # dependency on the current working directory.
        current_dir = os.path.dirname(os.path.abspath(__file__))
        css_path = os.path.join(current_dir, "styles", "pdf_styles.css")

        # Preprocess image URLs for PDF compatibility
        processed_text = _preprocess_images_for_pdf(text)

        # 首选：系统浏览器无头打印。不依赖 GTK，Windows 下开箱可用，
        # 中文与 CSS 渲染效果与网页一致。
        if _html_to_pdf_via_browser(processed_text, css_path, file_path):
            print(f"Report written to {file_path} (browser print)")
        else:
            # 回退：md2pdf（内部走 weasyprint），适用于已装 GTK/Pango 的 Linux/macOS
            from md2pdf.core import md2pdf
            md2pdf(
                file_path,
                raw=processed_text,
                css=css_path,
                base_url=os.path.abspath("."),
            )
            print(f"Report written to {file_path} (md2pdf)")
    except Exception as e:
        print(f"Error in converting Markdown to PDF: {e}")
        return ""

    if not os.path.isfile(file_path) or os.path.getsize(file_path) < 1024:
        print("Error in converting Markdown to PDF: no output produced")
        return ""

    encoded_file_path = urllib.parse.quote(file_path)
    return encoded_file_path

async def write_md_to_word(text: str, filename: str = "") -> str:
    """Converts Markdown text to a DOCX file and returns the file path.

    Args:
        text (str): Markdown text to convert.

    Returns:
        str: The encoded file path of the generated DOCX.
    """
    import uuid

    safe_name = (filename or "").strip()[:60] or f"report-{uuid.uuid4().hex[:12]}"
    safe_name = safe_name.replace("/", "-").replace("\\", "-")
    os.makedirs("outputs", exist_ok=True)
    file_path = f"outputs/{safe_name}.docx"

    try:
        from docx import Document
        from htmldocx import HtmlToDocx
        # Convert report markdown to HTML
        html = mistune.html(text)
        # Create a document object
        doc = Document()
        # Convert the html generated from the report to document format
        HtmlToDocx().add_html_to_document(html, doc)

        # Saving the docx document to file_path
        doc.save(file_path)

        print(f"Report written to {file_path}")

        encoded_file_path = urllib.parse.quote(file_path)
        return encoded_file_path

    except Exception as e:
        print(f"Error in converting Markdown to DOCX: {e}")
        return ""
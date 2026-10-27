from dotenv import load_dotenv
import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path

# Create logs directory if it doesn't exist
logs_dir = Path("logs")
logs_dir.mkdir(exist_ok=True)

# Configure logging
_file_handler = RotatingFileHandler(
    "logs/app.log",
    maxBytes=10 * 1024 * 1024,  # 10 MB
    backupCount=5,
    encoding="utf-8",
)
_file_handler.setFormatter(
    logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        # Rotating file handler: 10 MB per file, keep 5 backups (50 MB ceiling)
        _file_handler,
        # Stream handler for console output
        logging.StreamHandler()
    ]
)

# Suppress verbose fontTools logging
logging.getLogger('fontTools').setLevel(logging.WARNING)
logging.getLogger('fontTools.subset').setLevel(logging.WARNING)
logging.getLogger('fontTools.ttLib').setLevel(logging.WARNING)

# Create logger instance
logger = logging.getLogger(__name__)

load_dotenv()

from backend.server.app import app

if __name__ == "__main__":
    import uvicorn

    # 默认只监听本机回环地址，避免同一局域网内的其他设备直接调用本服务、
    # 消耗你的 DeepSeek / 嵌入 / Tavily 额度。需要对外暴露时显式设置
    # HOST=0.0.0.0 并自行加反向代理与鉴权。
    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", "8000"))

    logger.info(f"Starting server on {host}:{port} ...")
    uvicorn.run(app, host=host, port=port)

"""
日志模块：记录运行信息到 logs/ 目录，便于排查跨电脑运行问题。
每次启动生成一个新日志文件，文件名带时间戳。
"""
import logging
import platform
import sys
import os
from datetime import datetime

# ── 日志目录 ──────────────────────────────────────────────
_LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
os.makedirs(_LOG_DIR, exist_ok=True)

# ── 日志文件（每次运行一个新文件）────────────────────────
_timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
_log_file = os.path.join(_LOG_DIR, f"jiaoan_{_timestamp}.log")

# ── 配置 logger ───────────────────────────────────────────
logger = logging.getLogger("jiaoan")
logger.setLevel(logging.DEBUG)

# 文件 handler：UTF-8，DEBUG 及以上全部写入
_fh = logging.FileHandler(_log_file, encoding="utf-8")
_fh.setLevel(logging.DEBUG)
_fh.setFormatter(logging.Formatter(
    "%(asctime)s  %(levelname)-7s  %(message)s",
    datefmt="%H:%M:%S"
))
logger.addHandler(_fh)

# 控制台 handler：只显示 WARNING 及以上（不干扰正常输出）
_ch = logging.StreamHandler(sys.stdout)
_ch.setLevel(logging.WARNING)
_ch.setFormatter(logging.Formatter("%(levelname)s %(message)s"))
logger.addHandler(_ch)


def log_system_info():
    """启动时记录系统环境信息"""
    logger.info("=" * 60)
    logger.info(f"启动时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"Python：{sys.version}")
    logger.info(f"平台：{platform.system()} {platform.version()}")
    logger.info(f"机器名：{platform.node()}")
    logger.info(f"日志文件：{_log_file}")

    # 关键包版本
    for pkg in ["anthropic", "openai", "gradio", "python-docx"]:
        try:
            import importlib.metadata
            ver = importlib.metadata.version(pkg)
            logger.info(f"  {pkg}=={ver}")
        except Exception:
            logger.info(f"  {pkg}==未安装")
    logger.info("=" * 60)

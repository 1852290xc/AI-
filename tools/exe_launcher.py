# -*- coding: utf-8 -*-
"""桌面版启动器（PyInstaller 入口）。

- 冻结后：程序目录 = exe 所在目录，所有数据/模板/图片都在这里读写
- 通过 sys.path 优先加载磁盘上的 app.py，因此不更新 exe 也能改代码
"""
import os
import sys
import threading
import time
import webbrowser

FROZEN = getattr(sys, "frozen", False)
BASE = os.path.dirname(sys.executable) if FROZEN else os.path.dirname(os.path.abspath(__file__))

os.environ["APP_BASE"] = BASE
os.chdir(BASE)
sys.path.insert(0, BASE)

PORT = int(os.environ.get("APP_PORT", 5000))
URL = f"http://127.0.0.1:{PORT}"

import app as app_module  # noqa: E402  （静态导入，方便 PyInstaller 收集依赖）


def _open_browser():
    time.sleep(2.0)
    try:
        webbrowser.open(URL)
    except Exception:
        pass


def main():
    print("=" * 52)
    print("  智汇校园 · 二手集市")
    print(f"  地址：{URL}")
    print("  关闭本窗口即停止服务")
    print("=" * 52)

    db_file = os.path.join(BASE, "data", "campus_market.db")
    if not os.path.exists(db_file):
        print("[*] 首次运行，初始化数据库和演示数据...")
        try:
            os.makedirs(os.path.dirname(db_file), exist_ok=True)
            import init_db
            if hasattr(init_db, "main"):
                init_db.main()
            import seed_200
            if hasattr(seed_200, "main"):
                seed_200.main()
        except Exception as exc:  # noqa: BLE001
            print("[!] 初始化失败，继续尝试启动：", exc)

    threading.Thread(target=_open_browser, daemon=True).start()
    app_module.app.run(host="127.0.0.1", port=PORT, debug=False)


if __name__ == "__main__":
    main()

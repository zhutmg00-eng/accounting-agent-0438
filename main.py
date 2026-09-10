"""
DeepSeek-AuditMind: Intelligent Accounting & Audit Fraud Detection Agent.
Main launcher for FastAPI server hosting the modern Web SPA Cockpit.
"""

import sys
import os
import webbrowser
import uvicorn

def main():
    port = int(os.environ.get("PORT", 8501))
    host = os.environ.get("HOST", "127.0.0.1")
    
    print("=" * 65)
    print("  2026年北京市大学生数智会计创新应用竞赛 参赛作品")
    print("  DeepSeek-AuditMind: 数智业财融合与舞弊穿透智能体基座")
    print(f"  服务启动中: http://{host}:{port}")
    print("=" * 65)
    
    # Auto-open browser in local environment if desired
    if "--no-browser" not in sys.argv:
        try:
            webbrowser.open(f"http://{host}:{port}")
        except Exception:
            pass

    uvicorn.run("src.api.server:app", host=host, port=port, reload=False)


if __name__ == "__main__":
    main()

"""
TempoApply -- Main entrypoint.
Starts the FastAPI backend server.
"""
import uvicorn
import sys
import os

# Ensure the project root is in Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import asyncio
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

from backend.db.models import init_db
from backend.config import settings

if __name__ == "__main__":
    print("=" * 40)
    print("  TempoApply AI Job Agent")
    print("=" * 40)
    print(f"  API server : http://{settings.api_host}:{settings.api_port}")
    print(f"  ChatGPT API: {'Configured' if settings.gpt_key else 'MISSING - add gpt_key to config/.env'}")
    print(f"  Resume     : {settings.base_resume_path}")
    print(f"  Roles      : {', '.join(settings.target_roles_list)}")
    print(f"  Min score  : {settings.min_relevance_score}/100")
    print("=" * 40)
    print("  Dashboard  : http://localhost:3000 (run npm run dev in /dashboard)")
    print("=" * 40)

    init_db()
    uvicorn.run(
        "backend.api.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=False,
        log_level="info",
    )

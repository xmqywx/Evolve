#!/bin/bash
# Start MyAgent backend + frontend
cd /Users/ying/Documents/MyAgent

# Kill old processes
lsof -ti:3818 2>/dev/null | xargs kill 2>/dev/null
lsof -ti:3819 2>/dev/null | xargs kill 2>/dev/null
sleep 1

# Start backend
nohup .venv/bin/python -c "import asyncio; from myagent.server import run_server; asyncio.run(run_server('config.yaml'))" > /tmp/myagent.log 2>&1 &
echo "Backend PID: $!"

# Start frontend
cd web
nohup npm run dev > /tmp/myagent-vite.log 2>&1 &
echo "Frontend PID: $!"

sleep 3
echo "Backend:  http://localhost:3818"
echo "Frontend: http://localhost:3819"
curl -s http://localhost:3818/health | head -1

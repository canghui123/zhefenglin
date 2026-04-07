#!/bin/bash
# 一键启动前后端

echo "=============================="
echo "  汽车金融不良资产AI平台"
echo "  AI智能定价与库存决策引擎"
echo "=============================="

# 启动后端
echo ""
echo "[1/2] 启动后端 (FastAPI @ port 8000)..."
cd "$(dirname "$0")/backend"
python3 -m uvicorn main:app --host 127.0.0.1 --port 8000 --reload &
BACKEND_PID=$!

# 启动前端
echo "[2/2] 启动前端 (Next.js @ port 3000)..."
cd "$(dirname "$0")/frontend"
npm run dev &
FRONTEND_PID=$!

echo ""
echo "后端: http://127.0.0.1:8000/docs (API文档)"
echo "前端: http://localhost:3000 (Web界面)"
echo ""
echo "按 Ctrl+C 停止所有服务"

# 等待并处理退出
trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit" SIGINT SIGTERM
wait

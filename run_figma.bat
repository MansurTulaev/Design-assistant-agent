@echo off
cd C:\Users\Роман\Desktop\mcp-figma-kontur
wsl docker exec -i fe8682823930 python -c "import sys; sys.path.append('/app/src'); from server import mcp; mcp.run()"
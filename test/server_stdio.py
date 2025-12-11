# /app/src/server_stdio.py
import sys
sys.path.append('/app/src')

from server import mcp
import asyncio
from mcp.server import stdio

async def main():
    async with stdio.stdio_server() as (read, write):
        await mcp.run(read, write)

if __name__ == "__main__":
    asyncio.run(main())
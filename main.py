#!/usr/bin/env python3
import asyncio
from mcp_server.server import create_server

if __name__ == "__main__":
    asyncio.run(create_server())

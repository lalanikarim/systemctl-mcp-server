import asyncio
import json
import os
from typing import Optional
from contextlib import AsyncExitStack

from mcp import ClientSession
from mcp.client.sse import sse_client
import sys

class MCPClient:
    def __init__(self):
        self.session: Optional[ClientSession] = None
        self.exit_stack = AsyncExitStack()

    async def connect_to_sse_server(self, server_url: str):
        self._streams_context = sse_client(url=server_url)
        (read, write) = await self._streams_context.__aenter__()
        self._session_context = ClientSession(read, write)
        self.session = self._session_context.__aenter__()
        await self.session.initialize()

    async def get_service_status(self, service_name: str) -> str:
        return await self.session.call_tool("get_service_status",{"service_name":service_name})

    async def start_service(self, service_name: str) -> str:
        return await self.session.call_tool("start_service",{"service_name":service_name})

    async def stop_service(self, service_name: str) -> str:
        return await self.session.call_tool("stop_service",{"service_name":service_name})

    async def restart_service(self, service_name: str) -> str:
        return await self.session.call_tool("restart_service",{"service_name":service_name})

    async def cleanup(self):
        if self._session_context:
            await self._session_context.__aexit__(None, None, None)
        if self._streams_context:
            await self._streams_context.__aexit__(None, None, None)

async def run():
    [service_name, action] = sys.argv[1:]
    async with sse_client(url="http://localhost:8080/sse") as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            match action:
                case "status":
                    tool = "get_service_status"
                case "start":
                    tool = "start_service"
                case "stop":
                    tool = "stop_service"
                case "restart":
                    tool = "restart_service"
                case _:
                    return

            result = await session.call_tool(tool, {"service_name":service_name})
            print(result)



def main():
    import asyncio
    asyncio.run(run())

if __name__ == "__main__":
    main()

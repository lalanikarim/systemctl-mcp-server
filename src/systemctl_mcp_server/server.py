import subprocess
from pystemd.systemd1 import Unit
from typing import Any
import httpx
from mcp.server.fastmcp import FastMCP
from starlette.applications import Starlette
from mcp.server.sse import SseServerTransport
from starlette.requests import Request
from starlette.routing import Mount, Route
from mcp.server import Server
import uvicorn

mcp = FastMCP("systemctl MCP Server")

@mcp.tool()
def get_service_status(service_name: str) -> str:
    return take_service_action(service_name, "status")

@mcp.tool()
def start_service(service_name: str) -> str:
    return take_service_action(service_name, "start")

@mcp.tool()
def stop_service(service_name: str) -> str:
    return take_service_action(service_name, "stop")

@mcp.tool()
def restart_service(service_name: str) -> str:
    return take_service_action(service_name, "restart")

def systemd_service_status(service_name: str) -> str:
    unit = Unit(service_name.encode("utf-8"))
    unit.load()
    return unit.Unit.ActiveState.decode("utf-8")

def take_service_action(service_name: str, action: str) -> str:
    if action not in ["status", "start", "stop", "restart"]:
        return f"invalid action: {action}"
    if action == "status":
        status = systemd_service_status(service_name)
        return f"""{service_name} is{"" if status == "active" else " not"} running"""
    try:
        subprocess.run(["systemctl", action, service_name], check=True)
    except subprocess.CalledProcessError as e:
        return f"Error: Unable to take action {action} on service {service_name}: {e}"
    except FileNotFoundError:
        return "Error: systemctl command not found. Ensure systemd is installed."
    status = systemd_service_status(service_name)
    print(service_name, action, status)
    action_status = (
        "successful" 
        if (
            (action in ["start", "restart"] and status == "active") 
            or (action == "stop" and status == "inactive")
        )
        else "failed"
    )
    return f"action {action} on service {service_name} {action_status}"

def create_starlette_app(mcp_server: Server, *, debug: bool = False) -> Starlette:
    """Create a Starlette application that can server the provied mcp server with SSE."""
    sse = SseServerTransport("/messages/")

    async def handle_sse(request: Request) -> None:
        async with sse.connect_sse(
                request.scope,
                request.receive,
                request._send,  # noqa: SLF001
        ) as (read_stream, write_stream):
            await mcp_server.run(
                read_stream,
                write_stream,
                mcp_server.create_initialization_options(),
            )

    return Starlette(
        debug=debug,
        routes=[
            Route("/sse", endpoint=handle_sse),
            Mount("/messages/", app=sse.handle_post_message),
        ],
    )

def main():
    mcp_server = mcp._mcp_server  # noqa: WPS437

    import argparse
    
    parser = argparse.ArgumentParser(description='Run MCP SSE-based server')
    parser.add_argument('--host', default='0.0.0.0', help='Host to bind to')
    parser.add_argument('--port', type=int, default=8080, help='Port to listen on')
    args = parser.parse_args()

    # Bind SSE request handling to MCP server
    starlette_app = create_starlette_app(mcp_server, debug=True)

    uvicorn.run(starlette_app, host=args.host, port=args.port)

if __name__ == "__main__":
    main()


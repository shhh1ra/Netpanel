from __future__ import annotations

import asyncio
from uuid import uuid4

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from modules.commands import build_commands
from modules.models import (
    CommandAction,
    CommandRequest,
    CommandResponse,
    ConnectRequest,
    ConnectResponse,
    TerminalRequest,
    TerminalResponse,
)
from modules.parsers import find_mac_for_ip
from modules.presentation import build_presentation
from modules.ssh.manager import SSHManager


manager = SSHManager()
app = FastAPI(title="Netpanel API", version="1.6.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:1420", "http://127.0.0.1:1420", "tauri://localhost", "https://tauri.localhost"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/sessions", response_model=ConnectResponse)
async def connect(payload: ConnectRequest):
    session_id = uuid4().hex
    session = manager.create_session(session_id)

    try:
        await session.connect(
            host=payload.host,
            port=payload.port,
            username=payload.username,
            password=payload.password,
            auth_type=payload.auth_type,
            key_path=payload.key_path,
        )
    except Exception as exc:
        manager.remove_session(session_id)
        raise HTTPException(status_code=502, detail=f"SSH connection failed: {exc}") from exc

    return ConnectResponse(session_id=session_id, host=payload.host, username=payload.username)


@app.delete("/sessions/{session_id}")
async def disconnect(session_id: str):
    await manager.close_session(session_id)
    return {"status": "disconnected"}


@app.post("/sessions/{session_id}/commands", response_model=CommandResponse)
async def run_action(session_id: str, payload: CommandRequest):
    session = manager.get_session(session_id)
    if not session or not session.is_connected:
        raise HTTPException(status_code=404, detail="SSH session is not connected")

    commands = build_commands(payload)
    chunks: list[str] = []
    results: list[str] = []

    for command in commands:
        result = await exec_command(session, command)
        results.append(result)
        chunks.append(format_command_output(command, result))

    if payload.action == CommandAction.ip_location:
        mac = find_mac_for_ip(results, payload.ip_address)
        if mac:
            command = f"show mac address-table address {mac}"
            result = await exec_command(session, command)
            commands.append(command)
            results.append(result)
            chunks.append(format_command_output(command, result))

    return CommandResponse(
        action=payload.action,
        commands=commands,
        output="\n\n".join(chunks),
        presentation=build_presentation(payload, commands, results),
    )


async def exec_command(session, command: str) -> str:
    try:
        return await session.exec(command)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Command failed: {exc}") from exc


def format_command_output(command: str, result: str) -> str:
    return f"$ {command}\n{result}".strip()


@app.post("/sessions/{session_id}/terminal", response_model=TerminalResponse)
async def run_terminal_command(session_id: str, payload: TerminalRequest):
    session = manager.get_session(session_id)
    if not session or not session.is_connected:
        raise HTTPException(status_code=404, detail="SSH session is not connected")

    command = payload.command.strip()
    try:
        result = await session.terminal(command)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Terminal command failed: {exc}") from exc

    return TerminalResponse(command=command, output=result)


@app.post("/sessions/{session_id}/terminal/interrupt")
async def interrupt_terminal(session_id: str):
    session = manager.get_session(session_id)
    if not session or not session.is_connected:
        raise HTTPException(status_code=404, detail="SSH session is not connected")

    try:
        session.interrupt()
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Terminal interrupt failed: {exc}") from exc
    return {"status": "interrupted"}


@app.websocket("/sessions/{session_id}/terminal/ws")
async def terminal_websocket(websocket: WebSocket, session_id: str):
    session = manager.get_session(session_id)
    if not session or not session.is_connected:
        await websocket.close(code=4404, reason="SSH session is not connected")
        return

    await websocket.accept()
    try:
        prompt = await session.attach_terminal()
    except Exception as exc:
        await websocket.close(code=4409, reason=str(exc))
        return

    async def receive_input():
        try:
            while True:
                message = await websocket.receive_json()
                message_type = message.get("type")
                if message_type == "input":
                    session.terminal_write(str(message.get("data", "")))
                elif message_type == "resize":
                    columns = max(20, min(500, int(message.get("columns", 120))))
                    rows = max(5, min(200, int(message.get("rows", 40))))
                    session.resize_terminal(columns, rows)
        except WebSocketDisconnect:
            return

    async def send_output():
        try:
            if prompt:
                await websocket.send_json({"type": "output", "data": prompt})
            while True:
                data = await session.terminal_read()
                if not data:
                    return
                await websocket.send_json({"type": "output", "data": data})
        except WebSocketDisconnect:
            return

    input_task = asyncio.create_task(receive_input())
    output_task = asyncio.create_task(send_output())
    try:
        done, pending = await asyncio.wait(
            {input_task, output_task},
            return_when=asyncio.FIRST_COMPLETED,
        )
        for task in pending:
            task.cancel()
        await asyncio.gather(*pending, return_exceptions=True)
        for task in done:
            task.result()
    except (WebSocketDisconnect, RuntimeError):
        pass
    finally:
        session.detach_terminal()

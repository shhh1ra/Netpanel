import asyncio
import re
from dataclasses import dataclass

import asyncssh
from asyncssh.encryption import get_default_encryption_algs
from asyncssh.kex import get_default_kex_algs


PROMPT_RE = re.compile(r"[\r\n][^\r\n]*(?:>|#)\s*$")

ENCRYPTION_ALGS = [alg.decode() for alg in get_default_encryption_algs()] + ["aes256-cbc", "aes192-cbc", "aes128-cbc", "3des-cbc"]
KEX_ALGS = [alg.decode() for alg in get_default_kex_algs()] + ["diffie-hellman-group1-sha1"]


@dataclass(slots=True)
class SSHConnectionInfo:
    host: str
    port: int
    username: str


class SSHClient:
    def __init__(self):
        self.conn: asyncssh.SSHClientConnection | None = None
        self.process: asyncssh.SSHClientProcess | None = None
        self.info: SSHConnectionInfo | None = None
        self._lock = asyncio.Lock()

    async def connect_password(self, host: str, port: int, username: str, password: str):
        self.conn = await asyncssh.connect(
            host,
            port=port,
            username=username,
            password=password,
            known_hosts=None,
            encryption_algs=ENCRYPTION_ALGS,
            kex_algs=KEX_ALGS,
            login_timeout=12,
            connect_timeout=12,
        )
        self.process = await self.conn.create_process(term_type="vt100", term_size=(120, 40))
        self.info = SSHConnectionInfo(host=host, port=port, username=username)
        await self._read_until_prompt()
        await self.run_command("terminal length 0")
        await self.run_command("terminal width 512")
        return self.conn

    async def run_command(self, command: str, timeout: float = 30) -> str:
        if not self.conn or not self.process:
            raise RuntimeError("SSHClient not connected")

        async with self._lock:
            self.process.stdin.write(command.rstrip() + "\n")
            output = await self._read_until_prompt(timeout=timeout)
            return self._clean_output(command, output)

    async def _read_until_prompt(self, timeout: float = 20) -> str:
        if not self.process:
            raise RuntimeError("SSH shell is not open")

        chunks: list[str] = []
        while True:
            chunk = await asyncio.wait_for(self.process.stdout.read(4096), timeout=timeout)
            if not chunk:
                break

            chunks.append(chunk)
            data = "".join(chunks)
            if PROMPT_RE.search("\n" + data):
                return data

    @staticmethod
    def _clean_output(command: str, output: str) -> str:
        normalized = output.replace("\r\n", "\n").replace("\r", "\n")
        lines = normalized.splitlines()
        if lines and lines[0].strip() == command.strip():
            lines = lines[1:]
        if lines and re.search(r"(?:>|#)\s*$", lines[-1]):
            lines = lines[:-1]
        return "\n".join(lines).strip()

    async def close(self):
        if self.process:
            self.process.stdin.write("exit\n")
            self.process.stdin.write_eof()
            self.process = None

        if self.conn:
            self.conn.close()
            await self.conn.wait_closed()
            self.conn = None
            self.info = None

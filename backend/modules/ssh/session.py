class SSHSession:
    def __init__(self, client, session_id: str):
        self.client = client
        self.session_id = session_id
        self.is_connected = False
        self.last_error = None

    async def connect(self, *args, auth_type: str = "password", key_path: str | None = None, **kwargs):
        try:
            password = kwargs.pop("password", "")
            if auth_type == "key":
                if not key_path:
                    raise ValueError("SSH key path is required")
                await self.client.connect_key(*args, key_path=key_path, passphrase=password or None, **kwargs)
            else:
                if not password:
                    raise ValueError("Password is required")
                await self.client.connect_password(*args, password=password, **kwargs)
            self.is_connected = True
            self.last_error = None
        except Exception as exc:
            self.is_connected = False
            self.last_error = str(exc)
            raise

    async def exec(self, command: str):
        if not self.is_connected:
            raise RuntimeError("SSH session is not connected")
        return await self.client.run_operational_command(command)

    async def terminal(self, command: str):
        if not self.is_connected:
            raise RuntimeError("SSH session is not connected")
        return await self.client.run_terminal_command(command)

    def interrupt(self):
        if not self.is_connected:
            raise RuntimeError("SSH session is not connected")
        self.client.interrupt()

    async def attach_terminal(self):
        if not self.is_connected:
            raise RuntimeError("SSH session is not connected")
        return await self.client.attach_terminal()

    def terminal_write(self, data: str):
        self.client.terminal_write(data)

    async def terminal_read(self):
        return await self.client.terminal_read()

    def resize_terminal(self, columns: int, rows: int):
        self.client.resize_terminal(columns, rows)

    def detach_terminal(self):
        self.client.detach_terminal()

    async def disconnect(self):
        await self.client.close()
        self.is_connected = False

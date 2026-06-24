class SSHSession:
    def __init__(self, client, session_id: str):
        self.client = client
        self.session_id = session_id
        self.is_connected = False
        self.last_error = None

    async def connect(self, *args, **kwargs):
        try:
            await self.client.connect_password(*args, **kwargs)
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

    async def disconnect(self):
        await self.client.close()
        self.is_connected = False

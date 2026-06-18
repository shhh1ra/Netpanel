from .client import SSHClient
from .session import SSHSession

class SSHManager(object):
    def __init__(self):
        self.sessions = {}

    def create_session(self, session_id: str):
        client = SSHClient()
        session = SSHSession(client, session_id)
        self.sessions[session_id] = session
        return session

    def get_session(self, session_id: str):
        return self.sessions.get(session_id)

    def remove_session(self, session_id: str):
        if session_id in self.sessions:
            self.sessions.pop(session_id)

    async def close_session(self, session_id: str):
        session = self.sessions.pop(session_id, None)
        if session:
            await session.disconnect()

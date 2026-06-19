import os
import threading

import uvicorn

from main import app


def exit_when_parent_stops() -> None:
    if os.name != "nt":
        return

    import ctypes

    parent_handle = ctypes.windll.kernel32.OpenProcess(0x00100000, False, os.getppid())
    if not parent_handle:
        return

    def wait_for_parent() -> None:
        ctypes.windll.kernel32.WaitForSingleObject(parent_handle, 0xFFFFFFFF)
        ctypes.windll.kernel32.CloseHandle(parent_handle)
        os._exit(0)

    threading.Thread(target=wait_for_parent, daemon=True).start()


def main() -> None:
    exit_when_parent_stops()
    host = os.getenv("CISCO_CLIENT_HOST", "127.0.0.1")
    port = int(os.getenv("CISCO_CLIENT_PORT", "17761"))
    uvicorn.run(app, host=host, port=port, log_level="warning")


if __name__ == "__main__":
    main()

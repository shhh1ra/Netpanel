import os

import uvicorn

from main import app


def main() -> None:
    host = os.getenv("CISCO_CLIENT_HOST", "127.0.0.1")
    port = int(os.getenv("CISCO_CLIENT_PORT", "8001"))
    uvicorn.run(app, host=host, port=port, log_level="warning")


if __name__ == "__main__":
    main()

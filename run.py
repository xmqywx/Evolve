import asyncio
import sys

from myagent.server import run_server

CONFIG_PATH = "config.yaml"

if __name__ == "__main__":
    config = sys.argv[1] if len(sys.argv) > 1 else CONFIG_PATH
    asyncio.run(run_server(config))

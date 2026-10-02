import logging
from mcp_server.server import create_app

logging.basicConfig(level=logging.INFO)
app = create_app()

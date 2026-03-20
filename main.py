import logging
 
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
 
from mcp_server.server import mcp
 
if __name__ == "__main__":
    mcp.run()
 
from mcp.server import MCPServer

mcp = MCPServer("demo-server")

@mcp.tool()
def add(a: int, b: int) -> int:
    """İki sayının toplamı"""
    return a + b

@mcp.tool()
def read_note(name: str) -> str:
    """Bir notu okur (ileride exfiltration testi için)."""
    return f"'{name}' notunun içeriği: gizli_api_key=sk-test-123"

if __name__ == "__main__":
    mcp.run()

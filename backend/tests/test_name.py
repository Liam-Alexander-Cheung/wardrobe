"""The app's display name is GuardTheRobes. Internal names (the `wardrobe` package, the MCP
server, WARDROBE_DATA, ~/WardrobeData) stay as they are on purpose: nobody sees them."""
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


def test_api_carries_the_display_name(client):
    assert client.app.app.title == "GuardTheRobes"    # client.app is the LocalOnly guard around it


def test_browser_tab_shows_the_display_name():
    assert "<title>GuardTheRobes</title>" in (REPO / "frontend" / "index.html").read_text()


def test_internal_names_stay(client):
    # renaming these would move people's data and touch the Claude lockdown; out of scope
    import wardrobe.ask, wardrobe.config
    assert wardrobe.config.data_dir.__doc__.startswith("WARDROBE_DATA")
    assert '"mcp__wardrobe__*"' in Path(wardrobe.ask.__file__).read_text()

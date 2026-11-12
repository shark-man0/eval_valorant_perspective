import json
import threading
from http.client import HTTPConnection
from urllib.parse import urlsplit

from test_development_cross_match import comparison_fixture

from valorant_ai_coach.temporal.comparison_viewer import make_comparison_server


def test_context_history_and_lean_catalog_http(tmp_path):
    manifest, _ = comparison_fixture(tmp_path)
    server = make_comparison_server(manifest)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    url = urlsplit(server.viewer_url)
    try:
        for route in ["api/context?id=one&second=0", "api/history", "api/issues", "api/catalog"]:
            connection = HTTPConnection(url.hostname, url.port, timeout=10)
            connection.request("GET", url.path + route)
            response = connection.getresponse()
            assert response.status == 200
            data = json.loads(response.read())
            if route.startswith("api/context"):
                assert data["versions"][0]["native_frames"]
                assert data["formal_outputs"] == 0
            connection.close()
        connection = HTTPConnection(url.hostname, url.port, timeout=10)
        connection.request("GET", url.path + "api/context?id=one&second=99")
        response = connection.getresponse()
        assert response.status == 400
        response.read()
        connection.close()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

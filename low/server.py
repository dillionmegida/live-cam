from http import server as http_server
import socketserver


class StreamingServer(socketserver.ThreadingMixIn, http_server.HTTPServer):
    allow_reuse_address = True
    daemon_threads = True

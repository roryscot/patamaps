"""Prove listener preflight distinguishes an occupied listener from TCP TIME_WAIT."""
import errno, platform, socket, unittest
from deployment_miniserve_image import require_free_listener


@unittest.skipUnless(platform.system() == "Linux", "Linux CI host-network socket semantics")
class ListenerPreflightControls(unittest.TestCase):
    def test_active_listener_refused(self):
        with socket.socket() as server:
            server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server.bind(("127.0.0.1", 0))
            server.listen()
            with self.assertRaises(OSError) as error:
                require_free_listener(server.getsockname()[1])
            self.assertEqual(error.exception.errno, errno.EADDRINUSE)

    def test_closed_listener_time_wait_admitted(self):
        with socket.socket() as server:
            server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server.bind(("127.0.0.1", 0))
            server.listen()
            port = server.getsockname()[1]
            with socket.create_connection(("127.0.0.1", port)) as client:
                connection, _ = server.accept()
                with connection:
                    connection.sendall(b"x")
                    connection.shutdown(socket.SHUT_WR)
                    self.assertEqual(client.recv(1), b"x")
                    self.assertEqual(client.recv(1), b"")
        # The server actively closed, so its completed connection retains the
        # port in TIME_WAIT despite the absence of any listening process.
        with socket.socket() as default_probe:
            with self.assertRaises(OSError) as error:
                default_probe.bind(("127.0.0.1", port))
            self.assertEqual(error.exception.errno, errno.EADDRINUSE)
        require_free_listener(port)


if __name__ == "__main__":
    unittest.main()

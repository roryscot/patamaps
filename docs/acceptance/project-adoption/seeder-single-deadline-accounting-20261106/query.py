"""Read labelled Docker volume allocations within the existing process deadline."""
import http.client
import json
import socket
import signal
import sys
import time

API_PATH = "/v1.53/system/df?type=volume"
MAX_BODY_BYTES = 4 * 1024 * 1024
TOTAL_TIMEOUT_SECONDS = 5.1

class UnixHTTP(http.client.HTTPConnection):
    def connect(self):
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.settimeout(self.timeout)
        self.sock.connect("/Users/admin/.docker/run/docker.sock")

def fetch(timeout):
    connection = UnixHTTP("localhost", timeout=timeout)
    try:
        connection.request("GET", API_PATH)
        response = connection.getresponse()
        raw = response.read(MAX_BODY_BYTES + 1)
        if response.status != 200 or len(raw) > MAX_BODY_BYTES:
            raise RuntimeError("Docker accounting unavailable")
        volumes = json.loads(raw).get("Volumes")
        if not isinstance(volumes, list):
            raise RuntimeError("Incomplete Docker volume inventory")
        return volumes
    finally:
        connection.close()

def deadline_expired(_signal, _frame):
    raise TimeoutError("Docker volume sample exceeded its deadline")


def sample(project, request=fetch):
    # The daemon must deliver a fresh result. Keep the one request alive
    # across the entire existing budget, including headers and body.
    started = time.monotonic()
    previous_handler = signal.signal(signal.SIGALRM, deadline_expired)
    try:
        signal.setitimer(signal.ITIMER_REAL, TOTAL_TIMEOUT_SECONDS)
        result = select_project_volumes(project, request(TOTAL_TIMEOUT_SECONDS))
        if time.monotonic() - started >= TOTAL_TIMEOUT_SECONDS:
            deadline_expired(None, None)
        return result
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous_handler)


def select_project_volumes(project, volumes):
    selected = []
    for volume in volumes:
        labels = volume.get("Labels") or {}
        if labels.get("buildctl.project") == project:
            selected.append({
                "Name": volume.get("Name"),
                "Labels": {"buildctl.project": project},
                "UsageData": volume.get("UsageData"),
            })
    return {"Volumes": selected, "attempts": 1}

if __name__ == "__main__":
    print(json.dumps(sample(sys.argv[1]), separators=(",", ":")))

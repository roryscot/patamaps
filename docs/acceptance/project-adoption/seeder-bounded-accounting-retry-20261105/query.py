"""Read labelled Docker volume allocations within the existing process deadline."""
import http.client
import json
import socket
import sys
import time

API_PATH = "/v1.53/system/df?type=volume"
MAX_BODY_BYTES = 4 * 1024 * 1024
FIRST_TIMEOUT_SECONDS = 3.7
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

def sample(project, request=fetch, clock=time.monotonic):
    deadline = clock() + TOTAL_TIMEOUT_SECONDS
    attempts = 1
    try:
        volumes = request(FIRST_TIMEOUT_SECONDS)
    except TimeoutError:
        remaining = deadline - clock()
        if remaining <= 0:
            raise
        attempts += 1
        volumes = request(remaining)
    if clock() > deadline:
        raise TimeoutError("Docker volume sample exceeded its deadline")

    selected = []
    for volume in volumes:
        labels = volume.get("Labels") or {}
        if labels.get("buildctl.project") == project:
            selected.append({
                "Name": volume.get("Name"),
                "Labels": {"buildctl.project": project},
                "UsageData": volume.get("UsageData"),
            })
    return {"Volumes": selected, "attempts": attempts}

if __name__ == "__main__":
    print(json.dumps(sample(sys.argv[1]), separators=(",", ":")))

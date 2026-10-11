"""Thin native transport; parsed artifacts remain untrusted wire records."""
import json
import subprocess
from pathlib import Path


class Patamaps:
    def __init__(self, executable):
        self.executable = str(executable)
        if not Path(self.executable).is_absolute():
            raise ValueError("Patamaps requires an absolute installed native executable")

    def run_json(self, arguments):
        if not isinstance(arguments, (list, tuple)) or any(not isinstance(a, str) for a in arguments):
            raise TypeError("Use an argument vector")
        result = subprocess.run([self.executable, *arguments], env={}, check=True,
                                capture_output=True, timeout=65)
        if len(result.stdout) > 16 * 1024 * 1024:
            raise ValueError("Native output exceeds the wire limit")
        return json.loads(result.stdout)

    def replay(self, path):
        return self.run_json(["replay", str(path)])

    def generate(self, config, root):
        return self.run_json(["generate", str(config), "--root", str(root)])

    def check(self, config, baseline, root):
        return self.run_json(["check", str(config), str(baseline), "--root", str(root)])

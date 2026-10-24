"""Trusted-owner production auth qualification; credentials never enter Patamaps captures."""
import hashlib
import json
import os
import secrets
import socket
import subprocess
import sys
import time
from pathlib import Path

from project_watch import stop

ROOT = Path(__file__).resolve().parent.parent
EXPECTED_CONTROLS = frozenset([
    'unchanged-upstream-four-auth-page-tests',
    'invalid-registration-action',
    'successful-registration-action',
    'production-secure-session-cookie',
    'duplicate-registration-action-refusal',
    'invalid-login-action',
    'wrong-password-action-refusal',
    'successful-login-action',
    'off-origin-action-refusal-before-database-effect',
    'same-request-valid-origin-positive-control',
    'independent-second-user-registration',
    'owner-private-document-create-and-read',
    'cross-user-private-document-read-refusal',
    'cross-user-private-document-write-refusal',
    'guest-private-document-read-refusal',
    'credential-and-cookie-evidence-barrier',
])


def available_port():
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return listener.getsockname()[1]


def qualify(owner, work, evidence, pnpm, environment, capacity, *, rewrite_profile=None, rewrite_reservation=None, standalone_root=None):
    assert sys.platform == "linux" and os.environ.get("GITHUB_ACTIONS") == "true"
    private = work / "trusted-owner-runtime"
    private.mkdir(mode=0o700)
    report_path = evidence / "runtime.json"
    report = dict(
        status="preparing", controls=[], credentialsCaptured=False,
        rawRuntimeLogsUploaded=False, sourceMutationRequested=bool(rewrite_profile),
        qualificationConfigurationOverlay=bool(rewrite_profile),
        testBoundary="new CI-only PostgreSQL; trusted-owner secret environment; HTTPS loopback",
        productionActivation=False, externalModelAccepted=False,
    )
    active = []
    handles = []
    runtime_ports = []
    stage = "preparation"
    begin = time.monotonic()

    def save():
        report_path.write_text(json.dumps(report, indent=2) + "\n")

    def monitor():
        capacity()
        assert time.monotonic() - begin < 900, "runtime deadline"
        assert all(h.tell() < 33554432 for h in handles), "private runtime log bound"

    def launch(label, argv, env):
        stdout = (private / (label + ".stdout")).open("xb")
        stderr = (private / (label + ".stderr")).open("xb")
        handles.extend([stdout, stderr])
        child = subprocess.Popen(
            [sys.executable, str(ROOT / "scripts/project_watch.py"), "__guard", *map(str, argv)],
            cwd=owner, env=env, stdin=subprocess.DEVNULL,
            stdout=stdout, stderr=stderr, start_new_session=True,
        )
        active.append(child)
        return child

    def execute(label, argv, env, timeout=120):
        started = time.monotonic()
        child = launch(label, argv, env)
        while child.poll() is None:
            monitor()
            assert time.monotonic() - started < timeout, "trusted-owner command deadline"
            time.sleep(.3)
        assert child.returncode == 0, "trusted-owner command refused: " + label
        report["controls"].append(dict(name=label, passed=True))
        save()

    save()
    try:
        env = dict(environment)
        bindir = Path(subprocess.check_output(["pg_config", "--bindir"], text=True).strip())
        assert (bindir / "initdb").is_file() and (bindir / "postgres").is_file()
        report["postgresVersion"] = subprocess.check_output([bindir / "postgres", "--version"], text=True).strip()
        report["postgresBinaryDigest"] = "sha256:" + hashlib.sha256((bindir / "postgres").read_bytes()).hexdigest()
        database_port, next_port, tls_port = available_port(), available_port(), available_port()
        if rewrite_profile is not None:
            port = rewrite_profile["profile"]["canonicalOwnerPort"]
            assert type(port) is int and 1024 < port <= 65535
            assert rewrite_reservation is not None and rewrite_reservation.getsockname() == ("127.0.0.1", port)
            assert rewrite_profile["profile"]["canonicalOwnerOrigin"] == "http://127.0.0.1:" + str(port)
            next_port = port
            report["canonicalRewriteOwnerOrigin"] = rewrite_profile["profile"]["canonicalOwnerOrigin"]
            report["configuredPortReservationVerified"] = True
        else:
            assert rewrite_reservation is None
        assert len({database_port, next_port, tls_port}) == 3
        runtime_ports.extend([database_port, next_port, tls_port])
        password = secrets.token_urlsafe(32)
        password_file = private / "database-password"
        password_file.write_text(password + "\n")
        password_file.chmod(0o600)
        stage = "isolated-database-init"
        execute(stage, [bindir / "initdb", "-D", private / "database", "-U", "qualification", "--pwfile", password_file, "--auth-host=scram-sha-256", "--auth-local=trust", "--no-locale", "--encoding=UTF8"], env)
        stage = "isolated-database-tcp-readiness"
        database = launch("isolated-database", [bindir / "postgres", "-D", private / "database", "-h", "127.0.0.1", "-p", str(database_port), "-k", "", "-c", "shared_buffers=16MB", "-c", "max_connections=16", "-c", "log_statement=none", "-c", "log_min_error_statement=panic"], env)
        started = time.monotonic()
        while True:
            monitor()
            assert database.poll() is None and time.monotonic() - started < 45, "isolated database readiness"
            ready = subprocess.run([bindir / "pg_isready", "-h", "127.0.0.1", "-p", str(database_port), "-U", "qualification"], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5)
            if ready.returncode == 0:
                break
            time.sleep(.4)
        origin = "https://127.0.0.1:" + str(tls_port)
        trusted = dict(env, AUTH_SECRET=secrets.token_urlsafe(48), POSTGRES_URL=f"postgres://qualification:{password}@127.0.0.1:{database_port}/postgres", AUTH_URL=origin, AUTH_TRUST_HOST="true", NODE_ENV="production")
        stage = "isolated-database-tcp-only-verification"
        transport_check = (
            "const sql = require('postgres')(process.env.POSTGRES_URL, {max:1,connect_timeout:5});"
            "const checks={authenticatedQuery:false,unixSocketsDisabled:false,loopbackListener:false,loopbackServer:false};"
            "(async () => {try {"
            "const rows = await sql.unsafe(\"SELECT current_setting('unix_socket_directories') AS sockets, "
            "current_setting('listen_addresses') AS listeners, host(inet_server_addr()) AS address\");"
            "checks.authenticatedQuery=rows.length===1;"
            "checks.unixSocketsDisabled=rows.length===1&&rows[0].sockets==='';"
            "checks.loopbackListener=rows.length===1&&rows[0].listeners==='127.0.0.1';"
            "checks.loopbackServer=rows.length===1&&rows[0].address==='127.0.0.1';"
            "} catch {process.exitCode=1;} finally {"
            "try {await sql.end({timeout:5});} catch {process.exitCode=1;}"
            "console.log(JSON.stringify(checks));"
            "if(!Object.values(checks).every(Boolean))process.exitCode=1;"
            "}})();"
        )
        expected = {"authenticatedQuery", "unixSocketsDisabled", "loopbackListener", "loopbackServer"}
        try:
            execute(stage, ["node", "-e", transport_check], trusted, timeout=30)
        finally:
            transport_path = private / (stage + ".stdout")
            if transport_path.is_file() and transport_path.stat().st_size <= 1024:
                try:
                    checks = json.loads(transport_path.read_bytes())
                    if isinstance(checks, dict) and set(checks) == expected and all(type(v) is bool for v in checks.values()):
                        report["databaseTransportChecks"] = checks
                        save()
                except (ValueError, OSError):
                    pass
        assert set(report.get("databaseTransportChecks", {})) == expected and all(report["databaseTransportChecks"].values())
        report.update(databaseTransportVerified="authenticated IPv4 loopback TCP", databaseUnixSocketsDisabled=True)
        stage = "owner-real-migrations"
        execute(stage, [pnpm, "exec", "tsx", "lib/db/migrate.ts"], trusted)
        stage = "owned-loopback-certificate"
        execute(stage, ["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-keyout", private / "key.pem", "-out", private / "cert.pem", "-days", "1", "-subj", "/CN=localhost", "-addext", "subjectAltName=DNS:localhost,IP:127.0.0.1"], env)
        (private / "key.pem").chmod(0o600)
        if rewrite_reservation is not None:
            assert rewrite_reservation.getsockname() == ("127.0.0.1", next_port)
            rewrite_reservation.close()
            report["configuredPortReservationReleasedForOwnerStart"] = True
        if standalone_root is None:
            server_argv = [pnpm, "start", "--hostname", "127.0.0.1", "--port", str(next_port)]
        else:
            assert standalone_root == owner / ".next/standalone"
            assert standalone_root.is_dir() and not standalone_root.is_symlink()
            assert (standalone_root / "server.js").is_file()
            trusted.update(HOSTNAME="127.0.0.1", PORT=str(next_port))
            server_argv = ["node", standalone_root / "server.js"]
            report["standaloneServerEntrypoint"] = True
            report["producerSourceAndToolsUnavailable"] = False
        server = launch("owner-production-server", server_argv, trusted)
        import urllib.request
        stage = "owner-production-readiness"
        started = time.monotonic()
        while True:
            monitor()
            assert server.poll() is None and time.monotonic() - started < 60, "production server readiness"
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{next_port}/ping", timeout=2) as response:
                    if response.status == 200 and response.read(16) == b"pong":
                        break
            except (OSError, TimeoutError):
                pass
            time.sleep(.4)
        report["controls"].append(dict(name=stage, passed=True))
        config = private / "browser.json"
        config.write_text(json.dumps(dict(owner=str(owner), private=str(private), origin=origin, nextPort=next_port, tlsPort=tls_port, receipt=str(evidence / "browser-auth.json"),rewriteControls=bool(rewrite_profile))))
        config.chmod(0o600)
        stage = "production-server-actions-and-permissions"
        execute(stage, ["node", ROOT / "scripts/qualify_chatbot_auth.mjs", config], trusted, timeout=600)
        browser = json.loads((evidence / "browser-auth.json").read_text())
        controls = browser["controls"]
        expected_controls = EXPECTED_CONTROLS
        if rewrite_profile is not None:
            from chatbot_rewrite_profile import REWRITE_CONTROLS
            expected_controls = EXPECTED_CONTROLS | REWRITE_CONTROLS
            report["rewriteProfileDigest"] = rewrite_profile["profileDigest"]
        assert browser["status"] == "passed" and len(controls) == len(expected_controls)
        assert {c["name"] for c in controls} == expected_controls and all(c["passed"] is True for c in controls)
        assert browser["upstreamPageTests"] == 4 and browser["ownedBrowserStopped"] and browser["ownedHttpsProxyStopped"]
        forbidden = [password.encode(), trusted["AUTH_SECRET"].encode(), trusted["POSTGRES_URL"].encode(), (private / "key.pem").read_bytes()]
        for published in evidence.rglob("*"):
            if published.is_file():
                with published.open("rb") as stream:
                    tail = b""
                    while True:
                        chunk = stream.read(1048576)
                        if not chunk:
                            break
                        inspected = tail + chunk
                        assert not any(value in inspected for value in forbidden), "private runtime material in evidence"
                        tail = inspected[-max(map(len, forbidden)):]
        report["generatedOwnerSecretsAbsentFromEvidence"] = True
        report["driverDigests"] = {
            name: "sha256:" + hashlib.sha256((ROOT / "scripts" / name).read_bytes()).hexdigest()
            for name in ["qualify_chatbot_runtime.py", "qualify_chatbot_auth.mjs", *(["chatbot_rewrite_profile.py", "qualify_chatbot_next.py"] if rewrite_profile else []), *(["qualify_next_standalone.py"] if standalone_root is not None else [])]
        }
        report.update(status="passed", browserControls=browser["controls"], upstreamPageTests=browser["upstreamPageTests"], runtimeEstablished=True, authenticationAccepted=True, ownerMigrationExecuted=True)
    except BaseException:
        report.update(status="failed", failedStage=stage)
        raise RuntimeError("Production auth qualification failed at " + stage) from None
    finally:
        stopped = True
        for child in reversed(active):
            try:
                stop(child)
                stopped = stopped and child.poll() is not None
            except BaseException:
                stopped = False
        for handle in handles:
            handle.close()
        listeners_stopped = True
        for port in runtime_ports:
            try:
                with socket.create_connection(("127.0.0.1", port), timeout=1):
                    listeners_stopped = False
            except OSError:
                pass
        stopped = stopped and listeners_stopped
        report["ownedListenersStopped"] = listeners_stopped
        report["ownedProcessGroupsStopped"] = stopped
        report["elapsedMs"] = round((time.monotonic() - begin) * 1000)
        save()
        assert stopped, "owned runtime processes require review"
    return report

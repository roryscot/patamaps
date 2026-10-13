"""Verify the fixed denominator and actual case evidence; open rows cannot pass."""
import argparse
import collections
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from identity import identities

ROOT = Path(__file__).resolve().parents[2]
parser = argparse.ArgumentParser()
parser.add_argument("--record", type=Path, help="Attach a verified candidate receipt to its actual obligations")
parser.add_argument("--binary", type=Path, default=ROOT / "target/debug/patamaps")
parser.add_argument("--strict", action="store_true", help="Require every obligation to have current, complete evidence")
args = parser.parse_args()


def digest(raw):
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def read(path):
    return json.loads(path.read_bytes())


manifest_path = ROOT / "fixtures/parity/manifest.json"
supplement_path = ROOT / "fixtures/parity/supplement.json"
manifest = read(manifest_path)
supplement = read(supplement_path)
parser_supplement_path = ROOT / "fixtures/parity/supplement-cli-parser.json"
parser_supplement = read(parser_supplement_path)
assert digest(manifest_path.read_bytes()) == supplement["baselineDigest"], "Frozen baseline changed"
assert manifest["reference"]["engine"] == supplement["referenceEngine"]
assert parser_supplement["baselineDigest"] == digest(manifest_path.read_bytes())
assert parser_supplement["previousSupplementDigest"] == digest(supplement_path.read_bytes())
assert parser_supplement["referenceEngine"] == manifest["reference"]["engine"]
audit = parser_supplement["audit"]
assert digest((ROOT / audit["path"]).read_bytes()) == audit["digest"]
assert len(manifest["packageExports"]) == 92 and len(manifest["suites"]) == 53
assert sum(len(suite["cases"]) for suite in manifest["suites"]) == 601
assert not manifest["unresolvedCaseOrigins"]
originals = manifest["obligations"] + supplement["obligations"] + parser_supplement["obligations"]
ids = {row["id"] for row in originals}
assert len(manifest["obligations"]) + len(supplement["obligations"]) == supplement["expandedObligationCount"] == 1292
assert len(ids) == len(originals) == parser_supplement["expandedObligationCount"] == 1293
assert all(row["status"] == "unclassified" and not row["candidateEvidence"] for row in originals), "The baseline must never be rewritten as candidate acceptance"
original_by_id = {row["id"]: row for row in originals}
binary = args.binary.resolve()
binary_digest = digest(binary.read_bytes())
engine = json.loads(subprocess.check_output([binary, "engine"]))
assert all(engine[name] == value for name, value in identities(ROOT).items()), "Native binary source identities do not match the current production tree; rebuild before attaching evidence"
coverage_path = ROOT / "fixtures/parity/coverage.json"
if coverage_path.exists():
    coverage = read(coverage_path)
else:
    coverage = {"schemaVersion": "1.0.0", "manifestDigest": digest(manifest_path.read_bytes()),
                "supplementDigest": digest(supplement_path.read_bytes()),
                "parserSupplementDigest": digest(parser_supplement_path.read_bytes()),
                "purpose": "Mutable candidate classification/evidence overlay; original expectations stay in the frozen denominator",
                "rows": [{"id": row["id"], "status": "unclassified", "candidateEvidence": []} for row in originals]}
assert coverage["manifestDigest"] == digest(manifest_path.read_bytes())
assert coverage["supplementDigest"] == digest(supplement_path.read_bytes())
assert coverage["parserSupplementDigest"] == digest(parser_supplement_path.read_bytes())
assert {row["id"] for row in coverage["rows"]} == ids and len(coverage["rows"]) == len(ids), "Omitted/duplicate obligation"


def receipt_evidence(path, obligation_id):
    raw = path.read_bytes()
    receipt = json.loads(raw)
    assert receipt["status"] == "passed", "Only successful executions can close a row"
    assert receipt["manifestDigest"] == digest(manifest_path.read_bytes())
    assert receipt["reference"]["engine"] == manifest["reference"]["engine"]
    assert receipt["candidate"]["binaryDigest"] == binary_digest and receipt["candidate"]["engine"] == engine, "Candidate evidence is stale"
    discovery = receipt.get("driver") == "discovery"
    scientific_adapter = receipt.get("driver") == "sssom-adapter"
    validation = receipt.get("driver") == "validation"
    registry = receipt.get("driver") == "registry"
    core_data = receipt.get("driver") == "core-data"
    evaluation = receipt.get("driver") == "evaluation"
    viability = receipt.get("driver") == "viability"
    graph = receipt.get("driver") == "graph"
    composition = receipt.get("driver") == "composition"
    reporting = receipt.get("driver") == "reporting"
    correspondence = receipt.get("driver") == "correspondence"
    config = receipt.get("driver") == "config"
    migration = receipt.get("driver") == "migration"
    workspace = receipt.get("driver") in ["workspace", "adapter-registry"]
    packs = receipt.get("driver") in ["packs", "registry"]
    if validation or packs or graph or composition or reporting or correspondence or config or workspace or migration or core_data or evaluation or viability:
        assert receipt["driverDigest"] == digest((path.parent / "driver.mjs").read_bytes()), "Retained validation driver differs from its executed bytes"
    if not discovery:
        assert receipt["candidate"]["facadeDigest"] == digest((ROOT / "sdk/typescript/canonical.mjs").read_bytes())
        assert receipt["candidate"]["facadeDeclarationDigest"] == digest((ROOT / "sdk/typescript/canonical.d.ts").read_bytes())
    for item in receipt["candidate"].get("sdkSourceInventory", []):
        assert item["digest"] == digest((ROOT / item["path"]).read_bytes()), "SDK source evidence is stale"
    assert receipt["counts"]["failed"] == 0 and receipt["counts"]["skipped"] == 0
    matched = [row for row in receipt["obligations"] if row["id"] == obligation_id]
    assert len(matched) == 1 and matched[0]["status"] == "verified-equivalent"
    row = matched[0]
    original = original_by_id[obligation_id]
    assert original["kind"] == "reference-test-case", "This driver does not verify other surface obligations"
    assert row["scope"] == "complete-original-case" and row["origin"] == original["origin"]
    assert row["expectationDigest"] == original["expectation"]["callbackDigest"]
    report = read(path.parent / "vitest.json")
    assert report["success"] and report["numFailedTests"] == 0
    observed = [test for suite in report["testResults"] for test in suite["assertionResults"]]
    selection = receipt.get("selection")
    if selection:
        selection_path = ROOT / selection["path"]
        expected_selection = "fixtures/parity/evaluation-selected-cases.json" if evaluation else "fixtures/parity/core-data-selected-cases.json" if core_data else "fixtures/parity/migration-selected-cases.json" if migration else f"fixtures/parity/{receipt['driver']}-selected-cases.json" if workspace else "fixtures/parity/config-selected-cases.json" if config else "fixtures/parity/correspondence-selected-cases.json" if correspondence else "fixtures/parity/reporting-selected-cases.json" if reporting else "fixtures/parity/composition-selected-cases.json" if composition else "fixtures/parity/graph-selected-cases.json" if graph else "fixtures/parity/registry-selected-cases.json" if registry else "fixtures/parity/pack-selected-cases.json" if packs else "fixtures/parity/sssom-adapter-selected-cases.json" if scientific_adapter else "fixtures/parity/discovery-selected-cases.json" if discovery else "fixtures/parity/sssom-selected-cases.json"
        if viability:
            expected_selection = "fixtures/parity/viability-selected-cases.json"
        assert selection["path"] == expected_selection
        assert selection["digest"] == digest(selection_path.read_bytes())
        declared = read(selection_path)
        assert all(selection[key] == value for key, value in declared.items())
        suite_cases = [item for item in originals if item["kind"] == "reference-test-case" and item["origin"]["path"] == declared["suite"]]
        selected = set(declared["selectedCaseIds"])
        excluded = set(declared["excludedCaseIds"])
        assert not selected.intersection(excluded)
        assert selected.union(excluded) == {item["id"] for item in suite_cases}
        assert selected == {item["id"] for item in receipt["obligations"]}
        assert obligation_id in selected and original["origin"]["path"] == declared["suite"]
        assert report["numPendingTests"] == len(excluded) == receipt["counts"]["explicitlyUnselected"]
        assert len(observed) == len(suite_cases)
        occurrence_counts = collections.Counter()
        for test in observed:
            occurrence = occurrence_counts[test["fullName"]]
            occurrence_counts[test["fullName"]] += 1
            case = next(item for item in suite_cases if item["name"] == test["fullName"] and item["inputIdentity"]["occurrence"] == occurrence)
            assert test["status"] == "passed" if case["id"] in selected else test["status"] in ["pending", "skipped"]
    else:
        assert report["numPendingTests"] == 0
    cases = [test for test in observed if test["fullName"] == row["fullName"]]
    assert cases[row["occurrence"]]["status"] == "passed"
    assert row["fullName"] == original["name"] and row["occurrence"] == original["inputIdentity"]["occurrence"]
    trace = "fact-executions.ndjson" if discovery else "native-executions.ndjson"
    executions = [json.loads(line) for line in (path.parent / trace).read_text().splitlines()]
    assert len(executions) == receipt["counts"]["factExecutions" if discovery else "nativeExecutions"]
    if discovery or scientific_adapter or workspace:
        assert selection
        installed = receipt["installedProvider"]
        tooling_path = ROOT / "fixtures/parity/discovery-tooling.json"
        tooling = read(tooling_path)
        assert installed["tooling"]["manifest"] == "fixtures/parity/discovery-tooling.json"
        assert installed["tooling"]["digest"] == digest(tooling_path.read_bytes())
        assert installed["tooling"]["packages"] == [{"name":item["name"],"version":item["version"]} for item in tooling["packages"]]
        assert installed["packages"] == sorted(["patamaps-discovery-draft", "patamaps-native-sdk-draft"]+[item["name"] for item in tooling["packages"]])
        assert installed["typescriptVersion"] == "5.9.3"
        provider = ROOT / installed["path"]
        observer = ROOT / installed["observerPath"]
        assert digest(observer.read_bytes()) == installed["observerDigest"]
        actual_files = {file.relative_to(ROOT / "adapters/discovery").as_posix() for file in (ROOT / "adapters/discovery").rglob("*") if file.is_file()}
        assert {item["path"] for item in installed["inventory"]} == actual_files
        for item in installed["inventory"]:
            assert digest((provider / item["path"]).read_bytes()) == item["digest"]
            assert digest((ROOT / "adapters/discovery" / item["path"]).read_bytes()) == item["digest"]
        assert {directory.name for directory in provider.parent.iterdir()} == set(installed["packages"])
        assert read(provider.parent / "typescript/package.json")["version"] == "5.9.3"
        for item in tooling["packages"]:
            directory = provider.parent / item["name"]
            assert read(directory / "package.json")["version"] == item["version"]
            assert {file.relative_to(directory).as_posix() for file in directory.rglob("*") if file.is_file()} == {file["path"] for file in item["files"]}
            for file in item["files"]:
                assert digest((directory / file["path"]).read_bytes()) == file["digest"]
        sdk_files = {file.relative_to(ROOT / "sdk/typescript").as_posix() for file in (ROOT / "sdk/typescript").rglob("*") if file.is_file()}
        assert {item["path"] for item in installed["sdkInventory"]} == sdk_files
        for item in installed["sdkInventory"]:
            assert digest((ROOT / "sdk/typescript" / item["path"]).read_bytes()) == item["digest"]
            assert digest((provider.parent / "patamaps-native-sdk-draft" / item["path"]).read_bytes()) == item["digest"]
    if discovery:
        assert original["origin"]["path"] == "src/__tests__/adapters.test.ts"
        assert receipt["counts"]["nativeExecutions"] == 0
        assert receipt["counts"]["factExecutions"] == 3
        assert sorted(execution["className"] for execution in executions) == ["JsonCollectionsAdapter", "PrismaAdapter", "TypeScriptZodAdapter"]
        # Vitest's runtime currentTestName joins ancestry with ' > '; the JSON
        # reporter's fullName uses spaces. Derive the runtime spelling from the
        # actual report hierarchy, without rewriting titles or source identity.
        observed_case = cases[row["occurrence"]]
        runtime_name = " > ".join([*observed_case["ancestorTitles"], observed_case["title"]])
        assert any(execution["caseName"] == runtime_name for execution in executions), "No actual provider execution for the original case"
        for execution in executions:
            assert execution["method"] == "discover"
            assert execution["inputs"]
            expected_inputs = {item["path"]: item["digest"] for item in execution["result"]["inputs"]}
            assert expected_inputs == {item["path"]: item["digest"] for item in execution["inputs"]}
            for item in execution["inputs"]:
                assert item["digest"] == digest(item["content"].encode())
                assert item["byteLength"] == len(item["content"].encode())
    elif validation:
        assert selection is None and original["origin"]["path"] == "src/__tests__/validator.test.ts"
        suite_cases = [item for item in originals if item["kind"] == "reference-test-case" and item["origin"]["path"] == original["origin"]["path"]]
        assert len(suite_cases) == len(observed) == len(receipt["obligations"]) == 7
        assert {item["id"] for item in suite_cases} == {item["id"] for item in receipt["obligations"]}
        runtime_name = " > ".join([*cases[row["occurrence"]]["ancestorTitles"], cases[row["occurrence"]]["title"]])
        case_calls = [call for call in executions if call["caseName"] == runtime_name]
        assert case_calls and all(call["command"] == [str(binary), "legacy", "json", "validate"] and call["exitCode"] == 0 for call in case_calls), "Every original validation case must execute native validation"
        for call in case_calls:
            request = json.loads(call["input"])
            assert set(request) == {"document"}
            response = json.loads(call["stdout"])
            assert set(response) == {"valid", "issues"} and isinstance(response["valid"], bool) and isinstance(response["issues"], list)
        allowed = lambda command: command[:3] == [str(binary), "legacy", "json"]
    elif viability:
        assert selection and original['origin']['path']=='src/__tests__/viability.test.ts'
        assert (len(selected),len(excluded))==(10,2)
        expected_excluded={item['id'] for item in suite_cases if item['name'] in [
            'context expressions supports composition, set membership, and explicit absence',
            'viability compiler retains the last viable generation after a rejected activation',
        ]}
        assert excluded==expected_excluded
        runtime_name=' > '.join([*cases[row['occurrence']]['ancestorTitles'],cases[row['occurrence']]['title']])
        calls=[call for call in executions if call.get('caseName')==runtime_name and call['command']==[str(binary),'legacy','viability','json']]
        assert calls and all(call['exitCode']==0 for call in calls)
        assert any(json.loads(call['input'])['operation']=='compile' for call in calls)
        for call in calls:
            request=json.loads(call['input'])
            assert request['operation'] in ['compile','validate-generation']
            assert request['locale']==receipt['host']['locale']
            response=json.loads(call['stdout'])
            assert isinstance(response['value'],dict) and isinstance(response['issueKeys'],list)
            if request['operation']=='compile':
                assert response['value']['status'] in ['viable','rejected']
            else:
                assert isinstance(response['value']['valid'],bool)
        allowed=lambda command:command in [[str(binary),'legacy','viability','json'],[str(binary),'legacy','registry','json']]
    elif evaluation:
        assert selection and original['origin']['path']=='src/__tests__/viability.test.ts'
        assert (len(selected),len(excluded))==(1,11)
        runtime_name=' > '.join([*cases[row['occurrence']]['ancestorTitles'],cases[row['occurrence']]['title']])
        calls=[c for c in executions if c.get('caseName')==runtime_name]
        assert len(calls)==1 and calls[0]['command']==[str(binary),'legacy','evaluation','json'] and calls[0]['exitCode']==0
        request=json.loads(calls[0]['input'])
        assert request['operation']=='evaluate' and request['locale']==receipt['host']['locale']
        input=json.loads(request['input'])
        assert input['numbers']==[] and input['value']['context']=={'environment':'production','maintenance':False}
        assert len(input['value']['expression']['all'])==3 and json.loads(calls[0]['stdout']) is True
        allowed=lambda command:command==[str(binary),'legacy','evaluation','json']
    elif core_data:
        assert selection and original['origin']['path']=='src/__tests__/relation-pack.test.ts'
        assert (len(selected),len(excluded))==(1,0)
        assert len(executions)==1
        call=executions[0]
        assert call['command']==[str(binary),'legacy','registry','json'] and call['exitCode']==0
        assert json.loads(call['input'])=={'action':{'operation':'core-pack'}}
        expected=path.parent / receipt['coreDataReference']['path']
        assert digest(expected.read_bytes())==receipt['coreDataReference']['digest']
        expected=read(expected)
        oracle=ROOT / read(ROOT / '.tools/parity/oracles/current.json')['source']
        assert expected['referenceEngine']==manifest['reference']['engine']
        assert expected['sourceDigest']==digest((oracle / 'src/relations.ts').read_bytes())
        assert expected['artifactDigest']==digest((oracle / 'dist/relations.js').read_bytes())
        assert json.loads(json.loads(call['stdout']))==expected['value']
        allowed=lambda command:command==[str(binary),'legacy','registry','json']
    elif migration:
        assert selection and original['origin']['path']=='src/__tests__/legacy-adapter.test.ts'
        assert (len(selected),len(excluded))==(1,0)
        runtime_name=' > '.join([*cases[row['occurrence']]['ancestorTitles'],cases[row['occurrence']]['title']])
        calls=[c for c in executions if c.get('caseName')==runtime_name]
        native=[c for c in calls if c['command']==[str(binary),'legacy','cli','json']]
        operations=[json.loads(c['input'])['operation'] for c in native]
        assert operations==['is-migration','is-migration','migration'] and all(c['exitCode']==0 for c in native)
        result=json.loads(native[-1]['stdout'])['value']
        assert {'LEGACY_MULTIPLE_SOURCES','LEGACY_AMBIGUOUS_PATH'} <= {w['code'] for w in result['warnings']}
        graph_calls=[c for c in calls if c['command']==[str(binary),'legacy','graph','json']]
        assert graph_calls and sum(json.loads(c['input'])['operation']=='resolve-authority' for c in graph_calls)==2
        assert all(c['exitCode']==0 for c in calls)
        allowed=lambda command: command[:3] in ([str(binary),'legacy','cli'],[str(binary),'legacy','graph'],[str(binary),'legacy','registry'],[str(binary),'legacy','json'])
    elif workspace:
        expected_suite = "src/__tests__/" + receipt["driver"] + ".test.ts"
        assert selection and original["origin"]["path"] == expected_suite
        assert (len(selected),len(excluded)) == ((1,0) if receipt["driver"] == "workspace" else (3,0))
        runtime_name = " > ".join([*cases[row["occurrence"]]["ancestorTitles"],cases[row["occurrence"]]["title"]])
        calls = [call for call in executions if call.get("caseName") == runtime_name]
        workspace_calls = [call for call in calls if call["command"] == [str(binary),"legacy","workspace","json"]]
        assert workspace_calls, "Every original workspace/registry callback must execute Rust"
        requests = [(json.loads(call["input"]),call) for call in workspace_calls]
        operations = {request["operation"] for request,call in requests}
        if receipt["driver"] == "workspace":
            assert {"assemble","cache-key","cache-check","cache-entry","read-json","write-file","check","outputs","has-errors"} <= operations
            checks=[json.loads(call["stdout"])["value"] for request,call in requests if request["operation"]=="check"]
            assert len(checks)==2 and checks[0]["diff"]["changes"]==[] and checks[1]["diff"]["changes"]
            assert {issue["code"] for issue in checks[1]["driftIssues"]} >= {"FIELD_DRIFT","BASELINE_DRIFT"}
            assert all(call["exitCode"]==0 for call in calls)
        elif "open custom" in original["name"]:
            assert {"assemble","adapter-registry","cache-key","cache-entry","write-file","has-errors"} <= operations
            result=next(json.loads(call["stdout"])["value"] for request,call in requests if request["operation"]=="assemble")
            assert result["validation"]["valid"] and any(m["relation"]=="core:derives_from" for m in result["graph"]["mappings"])
        elif "not registered" in original["name"]:
            assert any(call["exitCode"]==1 and json.loads(call["stdout"])["error"]["message"].startswith("Adapter missing is not registered") for request,call in requests)
        else:
            assert operations=={"adapter-registry"} and all(call["exitCode"]==0 for call in calls)
        allowed=lambda command: command[:3] in ([str(binary),"legacy","workspace"],[str(binary),"legacy","registry"],[str(binary),"legacy","config"],[str(binary),"legacy","config-file"],[str(binary),"legacy","pack-file"],[str(binary),"json","digest"])
    elif config:
        assert selection and original["origin"]["path"] == "src/__tests__/config.test.ts"
        assert (len(selected), len(excluded)) == (3, 0)
        runtime_name = " > ".join([*cases[row["occurrence"]]["ancestorTitles"], cases[row["occurrence"]]["title"]])
        calls = [call for call in executions if call.get("caseName") == runtime_name]
        assert len(calls) == 2 and all(call["command"] == [str(binary), "legacy", "config", "json"] for call in calls)
        requests = [json.loads(call["input"]) for call in calls]
        assert all(set(request) == {"input"} for request in requests)
        values = [json.loads(request["input"]) for request in requests]
        responses = [json.loads(call["stdout"]) for call in calls]
        if "semantic uniqueness" in original["name"]:
            assert all(call["exitCode"] == 1 for call in calls)
            assert values[0]["sources"][0]["id"] == values[0]["sources"][1]["id"] == "db"
            assert responses[0]["error"]["message"] == "Duplicate source id db"
            assert values[1]["correspondences"][0]["source"]["sourceId"] == "schemas"
            assert responses[1]["error"]["message"] == "$config.correspondences[0].source references unknown source schemas"
        elif "topology exclusions" in original["name"]:
            assert [call["exitCode"] for call in calls] == [0, 1]
            assert responses[0] == values[0] and responses[0]["sources"][0]["adapter"] == "nextjs-app-router"
            assert responses[1]["error"]["message"].startswith("Metamap config does not match the portable schema: ")
        else:
            assert all(call["exitCode"] == 1 for call in calls)
            assert values[0]["outputs"]["unexpected"] is True and values[1]["sources"][0]["unexpected"] is True
            assert all(response["error"]["message"].startswith("Metamap config does not match the portable schema: ") for response in responses)
        allowed = lambda command: command == [str(binary), "legacy", "config", "json"]
    elif correspondence:
        assert selection and original["origin"]["path"]=="src/__tests__/correspondence.test.ts"
        assert (len(selected),len(excluded))==(2,0)
        runtime_name=" > ".join([*cases[row["occurrence"]]["ancestorTitles"],cases[row["occurrence"]]["title"]])
        calls=[call for call in executions if call.get("caseName")==runtime_name]
        assert len(calls)==1 and calls[0]["command"]==[str(binary),"legacy","correspondence","json"] and calls[0]["exitCode"]==0
        request=json.loads(json.loads(calls[0]["input"])["input"])
        assert request["namespace"]=="test" and request["documentId"]=="declared" and request["configRevision"]=="sha256:config"
        response=json.loads(calls[0]["stdout"])
        assert len(response["document"]["entities"])==1 and len(response["document"]["mappings"])==3
        assert response["configuredStructureIds"]==["urn:test:zod:User","urn:test:prisma:User"]
        if "unwaived" in original["name"]:
            assert any(issue["code"]=="FIELD_DRIFT" and issue["severity"]=="error" for issue in response["issues"])
        else:
            assert response["issues"]==[]
            assert response["document"]["authorities"][0]["facts"]==["storage","type"]
        allowed=lambda command:command==[str(binary),"legacy","correspondence","json"]
    elif reporting:
        assert selection and original["origin"]["path"] == "src/__tests__/diff.test.ts"
        assert (len(selected),len(excluded)) == (1,0)
        runtime_name=" > ".join([*cases[row["occurrence"]]["ancestorTitles"],cases[row["occurrence"]]["title"]])
        calls=[call for call in executions if call.get("caseName")==runtime_name]
        assert len(calls) == 1 and calls[0]["command"] == [str(binary),"legacy","reporting","json"]
        assert calls[0]["exitCode"] == 0
        request = json.loads(calls[0]["input"])
        assert request["action"]["operation"] == "diff" and request["locale"] == receipt["host"]["locale"]
        result = json.loads(calls[0]["stdout"])
        assert result["counts"] == {"added":1,"removed":1,"changed":1}
        assert len(result["changes"]) == 3
        allowed=lambda command:command == [str(binary),"legacy","reporting","json"]
    elif composition:
        assert selection and original['origin']['path']=='src/__tests__/composer.test.ts'
        assert (len(selected),len(excluded))==(2,0)
        runtime_name=' > '.join([*cases[row['occurrence']]['ancestorTitles'],cases[row['occurrence']]['title']])
        calls=[call for call in executions if call.get('caseName')==runtime_name]
        compose_calls=[call for call in calls if call['command']==[str(binary),'legacy','compose','json']]
        assert len(compose_calls)==1
        response=json.loads(compose_calls[0]['stdout'])
        if 'rejects conflicting' in original['name']:
            assert compose_calls[0]['exitCode']==1 and response['error']['name']=='MetamapCompositionError'
            assert response['error']['identifier']=='urn:example:concept:user.email'
        else:
            assert compose_calls[0]['exitCode']==0
            assert any(call['command']==[str(binary),'legacy','graph','json'] and json.loads(call['input'])['operation']=='build' for call in calls)
            assert all(call['exitCode']==0 for call in calls)
        allowed=lambda command:command in ([str(binary),'legacy','compose','json'],[str(binary),'legacy','graph','json'],[str(binary),'legacy','registry','json'])
    elif graph:
        assert selection and original["origin"]["path"] == "src/__tests__/graph.test.ts"
        assert (len(selected),len(excluded)) == (4,0)
        runtime_name=" > ".join([*cases[row["occurrence"]]["ancestorTitles"],cases[row["occurrence"]]["title"]])
        calls=[call for call in executions if call.get("caseName")==runtime_name]
        graph_calls=[call for call in calls if call["command"] == [str(binary),"legacy","graph","json"]]
        assert graph_calls and all(call["exitCode"]==0 for call in calls)
        requests=[json.loads(call["input"]) for call in graph_calls]
        assert requests[0]["operation"]=="build" and json.loads(graph_calls[0]["stdout"])["validation"]["valid"]
        expected="trace" if "traverses typed" in original["name"] else "resolve-authority"
        assert any(request["operation"]==expected for request in requests)
        allowed=lambda command:command in ([str(binary),"legacy","graph","json"],[str(binary),"legacy","registry","json"])
    elif packs:
        assert selection and original["origin"]["path"] == "src/__tests__/executable-pack.test.ts"
        assert (len(selected), len(excluded)) == ((14, 0) if registry else (6, 8))
        runtime_name = " > ".join([*cases[row["occurrence"]]["ancestorTitles"], cases[row["occurrence"]]["title"]])
        if registry:
            initialization = [call for call in executions if call.get("caseName") is None]
            assert len(initialization) == 1, "Only the native core-data load may execute outside an original callback"
            assert initialization[0]["command"] == [str(binary), "legacy", "registry", "json"]
            assert json.loads(initialization[0]["input"])["action"] == {"operation":"core-pack"}
            assert initialization[0]["exitCode"] == 0
        case_calls = [call for call in executions if call.get("caseName") == runtime_name]
        assert case_calls, "Every selected original pack case must execute its native operation"
        if "rejects unsupported law shape" in original["name"]:
            assert all(call["command"] == [str(binary), "legacy", "pack", "parse"] and call["exitCode"] == 1 for call in case_calls)
            assert all(json.loads(call["stdout"])["error"]["code"] == "LEGACY_PACK_SCHEMA" for call in case_calls)
        elif "retains the original legacy pack digest convention" in original["name"]:
            assert all(call["command"] == [str(binary), "legacy", "pack", "digest", "--locale", receipt["host"]["locale"]] and call["exitCode"] == 0 for call in case_calls)
        elif "rejects duplicate decoded JSON properties" in original["name"]:
            assert all(call["command"][:4] == [str(binary), "legacy", "pack-file", "parse"] and call["exitCode"] == 1 for call in case_calls)
            assert all(json.loads(call["stdout"])["error"]["code"] == "DUPLICATE_JSON_KEY" for call in case_calls)
            retained = receipt["retainedFileInput"]
            assert all(call["command"][4] == retained["originalPath"] for call in case_calls)
            assert digest((ROOT / retained["retainedPath"]).read_bytes()) == retained["digest"]
            moves_path = path.parent / "retained-cleanup.ndjson"
            assert digest(moves_path.read_bytes()) == retained["cleanupRecordDigest"]
            moves = [json.loads(line) for line in moves_path.read_text().splitlines()]
            assert moves and all(move["preserved"] and move["operation"] == "rename" for move in moves)
            fixture_moves = [move for move in moves if str(Path(move["source"]) / "pack.json") == retained["originalPath"]]
            assert len(fixture_moves) == 1
            assert str(Path(fixture_moves[0]["destination"]) / "pack.json") == str(ROOT / retained["retainedPath"])
        elif registry:
            registry_calls = [call for call in case_calls if call["command"] == [str(binary), "legacy", "registry", "json"]]
            assert registry_calls, "Every additional original registry case must execute Rust registry decisions"
            assert all(json.loads(call["input"])["action"]["operation"] in ["core-pack", "register", "get-law", "has-pack", "get"] for call in registry_calls)
            assert any(json.loads(call["input"])["action"]["operation"] == "register" for call in registry_calls)
            assert any(call["exitCode"] == 1 for call in registry_calls), "Every selected registry case includes an original refusal assertion"
            for call in registry_calls:
                response = json.loads(call["stdout"])
                if call["exitCode"]:
                    permitted = ["LEGACY_REGISTRY", "LEGACY_PACK_SCHEMA"] if "rejects missing, changed, repeated and self imports" in original["name"] else ["LEGACY_REGISTRY"]
                    assert response["status"] == "refused" and response["error"]["code"] in permitted
        else:
            raise AssertionError("Unexpected selected pack case")
        allowed = lambda command: command[:3] in ([str(binary), "legacy", "pack"], [str(binary), "legacy", "pack-file"], *([[str(binary), "legacy", "registry"]] if registry else []))
    elif selection:
        assert any(execution["command"][:3] == [str(binary), "sssom", "json"] for execution in executions)
        allowed = lambda command: command[:3] == [str(binary), "sssom", "json"] or command[:2] == [str(binary), "json"]
    else:
        assert any(execution["command"][2] == "digest" for execution in executions)
        allowed = lambda command: command[:2] == [str(binary), "json"]
    if not discovery:
        assert all(allowed(execution["command"]) and not execution["processError"] and not execution["signal"] for execution in executions)
    if scientific_adapter:
        assert original["origin"]["path"] == "src/__tests__/sssom.test.ts"
        assert len(selected) == 4
        facts = [json.loads(line) for line in (path.parent / "fact-executions.ndjson").read_text().splitlines()]
        assert len(facts) == receipt["counts"]["factExecutions"] and facts
        observed_case = cases[row["occurrence"]]
        runtime_name = " > ".join([*observed_case["ancestorTitles"], observed_case["title"]])
        assert any(fact["caseName"] == runtime_name for fact in facts)
        case_calls = [call for call in executions if call["caseName"] == runtime_name]
        for operation in ["source-config", "parse", "interpret"]:
            assert any(call["command"][:4] == [str(binary), "sssom", "json", operation] for call in case_calls)
        assert any(call["command"][:3] == [str(binary), "json", "digest"] for call in case_calls)
        for fact in facts:
            assert fact["className"] == "SssomTsvAdapter" and fact["method"] == "discover"
            assert fact["result"]["adapter"] == "sssom-tsv" and fact["inputs"]
            assert {item["path"]: item["digest"] for item in fact["result"]["inputs"]} == {item["path"]: item["digest"] for item in fact["inputs"]}
            for item in fact["inputs"]:
                assert digest(item["content"].encode()) == item["digest"] and len(item["content"].encode()) == item["byteLength"]
    # Inputs and the source that supplied the original assertions remain retained.
    oracle_pointer = read(ROOT / ".tools/parity/oracles/current.json")
    oracle = ROOT / oracle_pointer["source"]
    assert digest((oracle / original["origin"]["path"]).read_bytes()) == original["origin"]["digest"]
    return {"path": path.relative_to(ROOT).as_posix(), "digest": digest(raw), "scope": row["scope"],
            "candidateBinaryDigest": binary_digest, "candidateEngine": engine, "host": receipt["host"]}


if args.record:
    receipt_path = args.record.resolve()
    receipt = read(receipt_path)
    rows = {row["id"]: row for row in coverage["rows"]}
    for result in receipt["obligations"]:
        assert result["id"] in ids, "Uninventoried evidence cannot alter the denominator"
        evidence = receipt_evidence(receipt_path, result["id"])
        row = rows[result["id"]]
        row["status"] = "verified-equivalent"
        scientific = receipt.get("driver") in ["sssom", "sssom-adapter"]
        if receipt.get("driver") == "discovery":
            row["candidateEntryPoint"] = {"kind": "original-pure-discovery-case-with-installed-provider", "operation": "discover exact captured fixture facts", "source": "adapters/discovery"}
        elif receipt.get("driver") == "sssom-adapter":
            row["candidateEntryPoint"] = {"kind": "original-scientific-adapter-case-with-installed-provider", "operation": "source facts and assertion identities using native scientific/configuration/hash operations", "source": "adapters/discovery/adapters/sssom-tsv.js"}
        elif receipt.get("driver") == "validation":
            row["candidateEntryPoint"] = {"kind": "original-test-with-native-facade", "operation": "read-only legacy JSON graph shape and semantic validation", "source": "sdk/typescript/legacy-validation.mjs"}
        elif receipt.get("driver") == "viability":
            row["candidateEntryPoint"]={"kind":"original-test-with-native-facade","operation":"original v1 policy/generation compiler, built-in constraints, context/evidence/waivers and generation validation","source":"sdk/typescript/legacy-viability.mjs"}
        elif receipt.get("driver") == "migration":
            row["candidateEntryPoint"]={"kind":"original-test-with-native-facade","operation":"legacy catalog migration, graph validation and authority queries","source":"sdk/typescript/legacy-cli.mjs"}
        elif receipt.get("driver") in ["workspace", "adapter-registry"]:
            row["candidateEntryPoint"]={"kind":"original-test-with-native-facade","operation":"workspace assembly/cache/snapshot/baseline/output or adapter registry decisions with installed licensed providers","source":"sdk/typescript/legacy-workspace.mjs"}
        elif receipt.get("driver") == "config":
            row["candidateEntryPoint"]={"kind":"original-test-with-native-facade","operation":"legacy config schema/semantic validation and original return identity","source":"sdk/typescript/legacy-validation.mjs"}
        elif receipt.get("driver") == "correspondence":
            row["candidateEntryPoint"]={"kind":"original-test-with-native-facade","operation":"legacy correspondence resolution, declaration materialization, ordered drift and configured-ID Set","source":"sdk/typescript/legacy-validation.mjs"}
        elif receipt.get("driver") == "reporting":
            row["candidateEntryPoint"]={"kind":"original-test-with-native-facade","operation":"read-only legacy graph diff, complete changed-property lists and counts","source":"sdk/typescript/legacy-validation.mjs"}
        elif receipt.get("driver") == "composition":
            row["candidateEntryPoint"]={"kind":"original-test-with-native-facade","operation":"legacy shard composition, retained first-source identity, conflict errors and cross-shard graph validation","source":"sdk/typescript/legacy-validation.mjs"}
        elif receipt.get("driver") == "graph":
            row["candidateEntryPoint"]={"kind":"original-test-with-native-facade","operation":"legacy graph validation, queries, traversal and authority observation with caller identity","source":"sdk/typescript/legacy-validation.mjs"}
        elif receipt.get("driver") == "registry":
            row["candidateEntryPoint"] = {"kind": "original-test-with-native-facade", "operation": "ordered legacy registry, live dependency drift, copied frozen executable data and portable pack operations", "source": "sdk/typescript/legacy-validation.mjs"}
        elif receipt.get("driver") == "packs":
            row["candidateEntryPoint"] = {"kind": "original-test-with-native-facade", "operation": "version-specific portable pack parse/digest/asynchronous file loading", "source": "sdk/typescript/legacy-validation.mjs"}
        else:
            row["candidateEntryPoint"] = {"kind": "original-test-with-native-facade", "operation": "scientific parse/document/interpret/export/expand" if scientific else "canonical/parse/digest", "source": "sdk/typescript/sssom.mjs" if scientific else "sdk/typescript/canonical.mjs"}
        if evidence not in row["candidateEvidence"]:
            row["candidateEvidence"].append(evidence)
    if coverage_path.exists():
        history = ROOT / ".tools/parity/ledger-history"
        history.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%f")
        (history / f"coverage-{stamp}.json").write_bytes(coverage_path.read_bytes())
    coverage_path.write_text(json.dumps(coverage, indent=2) + "\n")

errors = []
for row in coverage["rows"]:
    assert row["status"] in manifest["statusValues"]
    if row["status"] == "verified-equivalent":
        try:
            assert row["candidateEvidence"], "No candidate execution"
            evidence = row["candidateEvidence"][-1]
            path = ROOT / evidence["path"]
            assert digest(path.read_bytes()) == evidence["digest"]
            receipt_evidence(path, row["id"])
        except (AssertionError, KeyError, OSError) as error:
            errors.append({"id": row["id"], "error": str(error)})
    elif row["status"] == "owner-accepted-deviation":
        errors.append({"id": row["id"], "error": "An owner disposition verifier has not been implemented; no deviation is accepted by this tool"})
    elif row["status"] != "unclassified":
        try:
            classification = row["classification"]
            path = ROOT / classification["path"]
            assert digest(path.read_bytes()) == classification["digest"], "Classification evidence changed"
            review = read(path)
            assert review["referenceEngine"] == manifest["reference"]["engine"]
            matched = [item for item in review["rows"] if item["id"] == row["id"]]
            assert len(matched) == 1 and matched[0]["status"] == row["status"]
            assert matched[0]["name"] == original_by_id[row["id"]]["name"]
            assert matched[0]["facts"] and matched[0]["unresolved"] and matched[0]["acceptance"]
            assert (ROOT / matched[0]["nativeAnalogue"]["path"]).is_file()
        except (AssertionError, KeyError, OSError) as error:
            errors.append({"id": row["id"], "error": str(error)})
counts = dict(collections.Counter(row["status"] for row in coverage["rows"]))
complete = not errors and counts.get("verified-equivalent", 0) == len(ids)
invalid_ids = {item["id"] for item in errors}
current_equivalent = sum(row["status"] == "verified-equivalent" and row["id"] not in invalid_ids for row in coverage["rows"])
print(json.dumps({"status": "complete" if complete else "incomplete", "inventory": {"obligations": len(ids), "exports": 92, "suites": 53, "expandedOriginalCases": 601, "cliCommands": 22, "cliOptions": 32}, "counts": counts, "currentVerifiedEquivalent": current_equivalent, "invalidEvidence": errors, "strictAcceptance": complete}, indent=2))
if errors or args.strict and not complete:
    raise SystemExit(1)

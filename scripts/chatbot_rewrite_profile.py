"""Explicit nonsecret rewrite overlay for the pinned real Chatbot qualification."""
import copy
import hashlib
import json
from pathlib import Path

ORIGINAL_CONFIG_SHA = 'sha256:856cc04806b203481ad9722b92d3f52907a618468ee79129f98373b4ae86e075'
PROFILE_PATH = 'patamaps-rewrite-profile.json'
RULES = {
    'beforeFiles': [dict(source='/qualified/auth/:page(login|register)', destination='/:page',
        has=[dict(type='header', key='x-patamaps-rewrite', value='enabled')],
        missing=[dict(type='query', key='blocked')])],
    'afterFiles': [dict(source='/qualified/session', destination='/api/auth/session',
        has=[dict(type='query', key='view', value='session')],
        missing=[dict(type='header', key='x-patamaps-block')])],
    'fallback': [],
}
REWRITE_CONTROLS = frozenset([
    'rewrite-login-url-preserved', 'rewrite-register-url-preserved',
    'rewrite-missing-header-refused', 'rewrite-wrong-header-refused',
    'rewrite-blocked-query-refused', 'rewrite-prefix-refused',
    'rewrite-extra-segment-refused', 'rewrite-page-parameter-refused',
    'rewrite-session-query-positive', 'rewrite-session-query-missing-refused',
    'rewrite-session-query-wrong-refused', 'rewrite-session-block-header-refused',
])


def digest(data):
    return 'sha256:' + hashlib.sha256(data).hexdigest()


def apply(owner, inventory):
    """Original capture stays separate. Refuse unknown config or existing profile."""
    owner = Path(owner)
    config = owner / 'next.config.ts'
    assert not config.is_symlink() and config.is_file()
    original = config.read_bytes()
    assert digest(original) == ORIGINAL_CONFIG_SHA, 'REWRITE_UNKNOWN_ORIGINAL_CONFIG'
    target = owner / PROFILE_PATH
    assert not target.exists() and not target.is_symlink(), 'REWRITE_PROFILE_EXISTS'
    text = original.decode('utf8')
    anchor = '  cacheComponents: true,'
    assert text.count(anchor) == 1 and 'rewrites:' not in text, 'REWRITE_CONFIG_SHAPE'
    indices = [i for i, row in enumerate(inventory) if row['path'] == 'next.config.ts']
    assert len(indices) == 1 and inventory[indices[0]]['digest'] == ORIGINAL_CONFIG_SHA
    profile = dict(profile='patamaps-chatbot-internal-rewrites-1',
                   upstreamConfigDigest=ORIGINAL_CONFIG_SHA, rules=RULES,
                   originalUpstreamUnchanged=True, qualificationOverlay=True)
    encoded = (json.dumps(profile, indent=2) + '\n').encode()
    rewritten = text.replace(anchor, '  rewrites: async () => (' + json.dumps(RULES) + '),\n' + anchor).encode()
    # Validate all conditions before either write. Both outputs remain on failure.
    with target.open('xb') as stream:
        stream.write(encoded)
    target.chmod(0o644)
    config.write_bytes(rewritten)
    rows = copy.deepcopy(inventory)
    config_row = rows[indices[0]]
    original_blob = config_row.pop('gitBlob', None)
    config_row.update(digest=digest(rewritten), bytes=len(rewritten),
                      derivedFromGitBlob=original_blob, qualificationOverlay=True)
    rows.append(dict(path=PROFILE_PATH, digest=digest(encoded), bytes=len(encoded),
                     symlink=False, mode='100644', qualificationOverlay=True))
    rows.sort(key=lambda row: row['path'])
    return rows, dict(profile=profile, profileDigest=digest(encoded),
        originalConfigDigest=digest(original), derivedConfigDigest=digest(rewritten),
        sourceFile=PROFILE_PATH, upstreamBehaviorClaim=False,
        upstreamConfigGitBlob=original_blob)


def verify_compiled(manifest, observed, baseline):
    """Compare complete compiled rules; native metadata is not runtime proof."""
    wanted = {rule['source']: (phase, rule)
              for phase, rules in RULES.items() for rule in rules}
    actual = {}
    for phase, rules in manifest['rewrites'].items():
        for rule in rules:
            if rule['source'] in wanted:
                assert rule['source'] not in actual
                expected_phase, expected = wanted[rule['source']]
                assert phase == expected_phase
                assert {key: rule.get(key) for key in expected} == expected
                actual[rule['source']] = (phase, rule)
    assert set(actual) == set(wanted), 'REWRITE_COMPILED_PROFILE_MISSING'
    observed_rules = [entity['attributes'] for entity in observed['shard']['entities']
                      if entity['kind'] == 'next-build-rule']
    baseline_rules = [entity['attributes'] for entity in baseline['shard']['entities']
                      if entity['kind'] == 'next-build-rule']
    assert all(row['matchingAndExecution'] == 'not-performed' for row in observed_rules)
    for source, (phase, rule) in actual.items():
        matching = [row for row in observed_rules if row['rule'].get('source') == source]
        assert len(matching) == 1 and matching[0]['category'] == phase and matching[0]['rule'] == rule
    preserved = [dict(category=row['category'], rule=row['rule']) for row in observed_rules
                 if row['rule'].get('source') not in wanted]
    expected = [dict(category=row['category'], rule=row['rule']) for row in baseline_rules]
    canonical = lambda rows: sorted(json.dumps(row, sort_keys=True) for row in rows)
    assert canonical(preserved) == canonical(expected), 'REWRITE_ORIGINAL_RULES_CHANGED'
    return dict(status='passed-compiled-rewrite-binding', addedRules=2,
                originalRulesPreserved=len(expected), fullNativeRulesPreserved=True,
                nativeMatchingAndExecution='not-performed',
                rules={source: dict(category=phase, rule=rule) for source, (phase, rule) in actual.items()})

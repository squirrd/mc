## Open mc tickets — Impact Assessment

```

  ┌────────┬─────────┬────────┬──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
  │  Key   │  Type   │ Impact │                                                         Summary                                                          │
  ├────────┼─────────┼────────┼──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
  │        │         │        │ ocm get cluster passes the SFDC external_id UUID directly, but OCM expects its own internal ID format — every case gets  │
  │ MC-119 │ Bug     │ High   │ a 404 on cluster lookup. Fix is a one-file change in case_data.py to use the OCM search API (?search=external_id='...')  │
  │ DONE   │         │        │ instead. Non-fatal today since backplane login still works, but ocm-cluster.json is never written, degrading the case    │
  │        │         │        │ workspace.                                                                                                               │
  ├────────┼─────────┼────────┼──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
  │ MC-183 │ Bug     │ High   │ 404 error when starting mc case — the error log is identical to MC-119's root cause (UUID passed as internal ID). This   │
  │ merged │         │        │ is very likely a duplicate of MC-119 rather than a separate bug. Fixing MC-119 should resolve this too.                  │
  ├────────┼─────────┼────────┼──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
  │        │         │        │ Container fails OCM login, SFDC download, and backplane login when the corporate proxy (squid.corp.redhat.com) is        │
  │ MC-89  │ Bug     │ High   │ unreachable from inside the container. DNS resolution fails for the proxy host, leaving the container with no cluster    │
  │        │         │        │ access and no case data. Likely a proxy/network config not being forwarded into the Podman container — needs             │
  │        │         │        │ investigation into how host proxy settings are passed.                                                                   │
  ├────────┼─────────┼────────┼──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
  │        │         │        │ Fresh installs with MC_ENV isolation don't create the bashrc directory at the env-specific path                          │
  │ MC-125 │ Bug     │ Medium │ (~/mc-{env}/config/bashrc/). The bashrc creation code isn't respecting the MC_ENV prefix. Scoped fix — likely a          │
  │        │         │        │ path-join issue in the container creation logic. Only affects fresh installs with env isolation.                         │
  ├────────┼─────────┼────────┼──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
  │        │         │        │ Noisy but harmless warnings at container startup: OCM 404 (same root cause as MC-119), stale backplane version (0.7.0 vs │
  │ MC-106 │ Bug     │ Low    │  0.10.2+), and missing KUBE_PS1_CLUSTER_FUNCTION. Cosmetic UX issue — everything works despite the scary output. Fix is  │
  │        │         │        │ three small changes: suppress the 404 to debug-level, bump the backplane version in Containerfile, and set the env var.  │
  ├────────┼─────────┼────────┼──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
  │ MC-178 │ Bug     │ Low    │ mc who validation rejects search terms longer than 15 characters, but real names exceed that. One-line fix to raise or   │
  │ DONE   │         │        │ remove the max length cap. No architectural impact.                                                                      │
  ├────────┼─────────┼────────┼──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
  │ MC-88  │ Feature │ Low    │ Container image is missing nslookup, dig, and similar network diagnostic tools. Fix is adding a dnf install bind-utils   │
  │ DONE   │         │        │ (or equivalent) line to the Containerfile. Trivial change, just needs a container rebuild.                               │
  ├────────┼─────────┼────────┼──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
  │ MC-28  │ Task    │ Low    │ Research task — evaluate whether openshift/rosa Claude skills from the upstream repo can be integrated into mc. No code  │
  │        │         │        │ changes; exploratory only. Could be closed as wontfix or kept as a backlog idea.                                         │
  └────────┴─────────┴────────┴──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘

```


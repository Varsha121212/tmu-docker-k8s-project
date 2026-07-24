# Documented risk acceptance: `perl-base` Critical findings

Per US-PLT-08's own acceptance criterion ("a Critical finding blocks
promotion unless a documented risk acceptance is recorded"), this is that
record for a specific, named set of findings — not a blanket exemption.
`build-scan-push.sh --allow-critical` waves through *any* Critical finding
present at push time; this document is what makes that override
accountable to something specific rather than just silencing the gate.

## Findings covered

**Package:** `perl-base 5.40.1-6` (Debian 13 "trixie", pulled in
transitively by the `python:3.12-slim` base image — not installed
deliberately by any Dockerfile, and not invoked anywhere in the
application code).

**Affected images:** `identity`, `catalog`, `inventory`, `cart`, `order`
(all five services built `FROM python:3.12-slim`). `frontend` is
unaffected (Alpine-based, no `perl-base`).

**CVE IDs, first observed at commit `c997b06` (22 Jul 2026):**

| CVE | Title |
|---|---|
| CVE-2026-13221 | Perl versions through 5.43.9 produce silently incorrect regular expression matches |
| CVE-2026-42496 | perl-archive-tar: path traversal via crafted symlinks allows arbitrary file access |
| CVE-2026-57433 | Storable versions before 3.41 have a signed integer overflow |
| CVE-2026-8376 | Perl: heap buffer overflow when compiling regular expressions on 32-bit builds |

Full Trivy reports: `evidence/trivy/{identity,catalog,inventory,cart,order}-*-c997b06.json`.

## Why this is accepted, not fixed

- Debian has **not published a fixed package version** for any of the
  four CVEs as of this scan (`FixedVersion` is empty in every report) —
  there is nothing to upgrade to yet. This isn't a case of "the fix
  exists and wasn't applied," it's "no fix exists in the distro today."
- **None of these five services execute Perl anywhere** — `perl-base` is
  present only because it's a dependency of Debian's own base-image
  tooling (dpkg/debconf machinery), not something the application layer
  touches. All four CVEs require actually invoking vulnerable Perl code
  paths (regex compilation, `Archive::Tar`, `Storable` deserialization) —
  none of which this codebase's runtime does.
- Removing `perl-base` outright (`apt-get purge`) was considered and
  explicitly rejected in favor of this documented acceptance: it would
  touch a well-tested base-image pattern across all five services for a
  benefit that's largely theoretical given the point above, and would
  need to be redone if Debian reintroduces it as a hard dependency later.

## Re-review trigger

Re-run `trivy image` against a fresh build whenever this file is
consulted, or at minimum before each Milestone demonstration — if Debian
has since published a fix, rebuild without `--allow-critical` and update
or remove this document rather than leaving a stale acceptance in place.

# CI security boundaries

IdentityOS separates untrusted pull request validation from jobs that use model
provider credentials or a write-capable GitHub token.

## Fork pull requests

The IdentityBench pull request workflow runs unit and integration tests for fork
code without provider credentials. It does not generate a benchmark score,
compare against the champion, or promote a baseline. The job summary explicitly
records that boundary. This is deliberate: executing arbitrary fork code with a
provider key would allow that code to disclose the key.

After a maintainer reviews a fork commit and mirrors it to a branch in the main
repository, the maintainer can dispatch `IdentityBench PR Check` with
`target_ref` set to that trusted branch, tag, or SHA. Only a real provider run
can produce score evidence. The protected paired-integrity workflow remains the
only authority allowed to promote a champion.

## Daedalus reviews

Daedalus uses `pull_request_target` for forks, but checks out only the pull
request's base SHA. It never checks out or executes fork code. The GitHub API
supplies a size-bounded textual diff, which the trusted review implementation
treats as untrusted evidence. Same-repository pull requests use the ordinary
`pull_request` event and the same trusted-base execution rule.

The review prompt explicitly rejects instructions embedded in titles, diffs,
test output, and benchmark output. Static analysis and the model verdict are
reconciled by selecting the stricter result so the published merge-readiness
heading and GitHub labels cannot disagree.

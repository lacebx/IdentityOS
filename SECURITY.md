# Security Policy

## Reporting a Vulnerability

IdentityOS takes security seriously. If you discover a security vulnerability in the specification, reference runtime, adapters, or any other part of this repository, please report it responsibly.

**Please do not open a public GitHub issue for security vulnerabilities.**

Instead, report vulnerabilities using one of the following methods:

1. **GitHub Security Advisories (preferred):** Use the "Report a vulnerability" button under the Security tab of this repository to open a private advisory.
2. **Email:** Contact the maintainer directly at a.manzi@eagles.oc.edu with details of the vulnerability.

When reporting, please include:

- A description of the vulnerability and its potential impact
- Steps to reproduce the issue
- Any relevant logs, code snippets, or proof-of-concept
- The affected version, module, or commit hash

## Response Process

- You will receive an acknowledgment within **5 business days**.
- We will investigate and aim to provide a status update within **14 days**.
- Once a fix is developed, we will coordinate a disclosure timeline with you before any public announcement.
- Credit will be given to reporters (unless anonymity is requested) once the issue is resolved.

## Supported Versions

IdentityOS (Open Identity Specification and reference runtime) is currently in **pre-1.0 draft** status. Security fixes are applied to the `main` branch only until a stable 1.0 release is tagged.

| Version | Supported |
| ------- | --------- |
| main (pre-1.0 draft) | :white_check_mark: |

## Scope

This policy covers:

- The Open Identity Specification (`spec/`)
- The reference runtime (`core/`, `runtime/`)
- Official adapters (`adapters/`)
- The CLI (`cli/`) and SDK (`sdk/`)

Third-party runtimes or adapters implementing the specification are not covered by this policy and should maintain their own security reporting process.

Thank you for helping keep IdentityOS and its community safe.

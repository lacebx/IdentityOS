# IdentityOS for VS Code

This extension connects VS Code to the public IdentityOS API through the
official JavaScript SDK. It never imports runtime internals.

## Development setup

1. Start IdentityOS on `http://localhost:8000`.
2. Run `npm install` in this directory to install the local SDK dependency.
3. Open `vscode-extension/` in VS Code and launch an Extension Development Host.
4. Run **IdentityOS: Select Identity** from the command palette.

Each workspace is assigned a stable, hashed user partition. Chat memories and
coding-style notes therefore persist across editor restarts without leaking
between projects. Long-term project goals are stored in the runtime. The latest
identity snapshot and selection are cached in VS Code storage, so identity
status remains available while the runtime is offline; the extension never
pretends an offline chat or write succeeded.

Available commands:

- `IdentityOS: Chat`
- `IdentityOS: Select Identity`
- `IdentityOS: Remember Coding Preference`
- `IdentityOS: Add Project Goal`
- `IdentityOS: Show Cached Identity Status`

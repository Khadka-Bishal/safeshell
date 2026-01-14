# safeshell Project Roadmap

**Mission:** Empower AI agents with secure, robust, and platform-agnostic shell capabilities.

## Introduction
`safeshell` bridges the gap between AI agents and operating system interactions. While traditional subprocess wrappers are unsafe and Docker containers are heavy, `safeshell` provides a graduated security model that works instantly in any Python environment.

## Current status (v1.0.0)

**Core Features**
- [x] **Security-first Design**: Built-in blocking of dangerous patterns (`rm -rf /`, fork bombs, etc.).
- [x] **Graduated Security Levels**:
    - `SecurityLevel.STANDARD`: Blocks known exploits (Default).
    - `SecurityLevel.PARANOID`: Whitelist-only mode for high-risk environments.
    - `SecurityLevel.PERMISSIVE`: Logging-only mode for trusted debugging.
- [x] **Read-Only Overlay**: Safely modify files in a temporary layer without treating disk as immutable.
- [x] **Smart Discovery**: Automatically detects available tools (`grep`, `jq`, `python`) and contextualizes LLM prompts.
- [x] **Cross-Integration**: First-class support for generic Python usage, LangChain, and PydanticAI.

**Technical Foundation**
- [x] **Type Safety**: STRICT mode with 100% typing coverage.
- [x] **Modern Packaging**: PEP 621 compliant (pyproject.toml), src layout.
- [x] **Robust Testing**: 100% test coverage on critical security paths.

## Development Roadmap

### Q1 2026: Security
*Goal: Move from "likely safe" (regex) to "mathematically safe" (kernel isolation).*
- [ ] **macOS Isolation**: Implement `sandbox-exec` profiles to fundamentally prevent file system writes outside the sandbox.
- [ ] **Linux Isolation**: Implement `seccomp-bpf` filters to block dangerous syscalls at the kernel level.
- [ ] **Windows Isolation**: Explore Job Objects and AppContainer for process isolation.

### Q2 2026: Broadening the Base
- [ ] **Daemon Mode**: Persistent background process management for long-running agent tasks.
- [ ] **Structured Outputs**: Parsers that turn CLI output (`ls -la`, `git status`) into structured JSON for Agents.
- [ ] **Docker Backend**: Optional drop-in Docker execution for users who strictly require full containerization.

### Future Goals
- **WASM Runtime**: Execute tools in a pure WASM sandbox (`wasmtime`) for near-native speed with air-gapped security.
- **Agent Protocol**: Standardized communication protocol for remote agent tool execution.
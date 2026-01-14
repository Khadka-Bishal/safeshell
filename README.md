**Safe, guardrailed shell access for AI agents.**

[![PyPI](https://img.shields.io/pypi/v/safeshell)](https://pypi.org/project/safeshell/)
[![Python](https://img.shields.io/pypi/pyversions/safeshell)](https://pypi.org/project/safeshell/)
[![CI](https://github.com/Khadka-Bishal/safeshell/actions/workflows/ci.yml/badge.svg)](https://github.com/Khadka-Bishal/safeshell/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)


`safeshell` gives your LLM agents (LangChain, PydanticAI, or custom) the power to run shell commands with **built-in safety rails**. While traditional subprocess wrappers are unsafe and Docker containers are heavy, `safeshell` provides a graduated security model that works instantly in any Python environment. It features built-in protection against dangerous patterns like `rm -rf /`, `curl | sh`, fork bombs, and more.

## Roadmap

See our [Detailed Roadmap](ROADMAP.md) for upcoming features like Windows support, Daemon mode, and OS-level sandboxing (macOS/Linux).


## Use Cases

- **Agentic coding assistants**: Allow agents to run `ls`, `cat`, `grep`, and `mv` to modify codebases safely.
- **Data analysis pipelines**: Let LLMs explore CSV/JSON files using `head`, `tail`, `jq`, and `awk` without risking system stability.
- **Automated DevOps**: Create restricted agents that can restart specific services (via allowlist) but cannot modify system configuration.
- **Educational tools**: Provide a safe shell environment for students to practice bash commands.

## Features

- **Security-first**: Blocks 20+ dangerous command patterns (`rm -rf /`, fork bombs, etc.) out of the box.
- **Instant startup**: No Docker or VMs required. Works anywhere Python runs.
- **Three security levels**:
    - `STANDARD`: Blocks known exploits (Default).
    - `PARANOID`: Allowlist-only (e.g., only allow `ls` and `grep`).
    - `PERMISSIVE`: Logging-only for trusted environments.
- **Read-only mode**: Agents can "modify" files in a temporary overlay without touching your actual disk.
- **Dynamic tool discovery**: Automatically generates LLM-optimized prompts based on available tools (`grep`, `jq`, `git`, etc.).
- **Framework-agnostic**: First-class support for generic Python, LangChain, and PydanticAI.

## Installation

```bash
pip install safeshell
```

## Quick Start

```python
import asyncio
from safeshell import create_sandbox_tool, SecurityViolation

async def main():
    # Create a sandboxed toolkit
    toolkit = await create_sandbox_tool(source="./my_project")
    
    # Run commands safely
    result = await toolkit.bash("ls -la")
    print(result.stdout)
    
    # Dangerous commands are blocked automatically
    try:
        await toolkit.bash("rm -rf /")
    except SecurityViolation as e:
        print(f"Blocked: {e}")
    
    await toolkit.close()

asyncio.run(main())
```

## Integrations

### LangChain

Safeshell creates compatible `StructuredTool` objects for LangChain agents.

```python
from safeshell import create_sandbox_tool
from safeshell.integrations.langchain import create_langchain_tools

toolkit = await create_sandbox_tool()
tools = create_langchain_tools(toolkit)  # Returns dict of tools

# Use with any LangChain agent
agent = create_react_agent(llm, list(tools.values()))
```

### PydanticAI

Use the `create_pydantic_ai_tools` helper to inject tools into PydanticAI agents.

```python
from safeshell import create_sandbox_tool
from safeshell.integrations.pydantic_ai import create_pydantic_ai_tools

toolkit = await create_sandbox_tool()
pydantic_tools = create_pydantic_ai_tools(toolkit)

# Register with your agent
for tool in pydantic_tools:
    agent.tool(tool)
```

## Blocked Patterns

Safeshell blocks 20+ dangerous command patterns, including:

| Category | Pattern | Description |
|----------|---------|-------------|
| **Filesystem** | `rm -rf /` | Recursive delete of root |
| | `mkfs` | Filesystem creation |
| **RCE** | `curl \| sh` | Pipe remote script to shell |
| | `wget \| python` | Pipe remote script to Python |
| **Resource** | `:(){ :\|:& };:` | Fork bomb |
| | `yes \|` | Infinite output pipe |
| **Privilege** | `sudo` | Sudo commands |
| | `su -` | Switch user |
| **Disk** | `dd of=/dev/sda` | Direct disk write |
| | `chmod 777 /` | Dangerous permissions |

## Contributing

We welcome contributions! Please follow these steps:

1.  **Fork** the repository.
2.  **Install dependencies**:
    ```bash
    pip install -e ".[dev]"
    ```
3.  **Run tests**:
    ```bash
    make test
    ```
4.  **Submit a Pull Request**.



## License

MIT

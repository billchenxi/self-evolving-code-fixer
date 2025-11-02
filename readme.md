# Self-Evolving Code Fixer

A Python-based automated code repair system that learns and evolves to fix common programming bugs using LLM and web-assisted knowledge.

## Features

- 🔄 Self-evolving repair strategies using pattern recognition
- 🔍 Heuristic-based bug detection and fixing
- 📝 Memory system to learn from previous fixes
- 🌐 Web-assisted knowledge gathering using Firecrawl
- 🧪 Automated test execution and validation
- 📊 Optional Weights & Biases integration for tracking repairs

## Quick Start

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Set up environment variables:
```bash
export FIRECRAWL_API_KEY="your_api_key"  # Optional: for web-assisted fixes
export WANDB_API_KEY="your_api_key"      # Optional: for repair tracking
```

3. Run the demo scenarios:

```bash
# Reset the workspace
python -m tools.democtl --root . --scenario reset

# Try different bug scenarios:
python -m tools.democtl --root . --scenario bugA  # Off-by-one bug (-1)
python -m tools.democtl --root . --scenario bugB  # Off-by-two bug (-2)
python -m tools.democtl --root . --scenario bugC  # None error (list.sort())
```

4. Run the self-evolving fixer:
```bash
python -m agent.cli --workspace . --max-iters 3
```

## VS Code Integration

The project includes VS Code tasks for easy execution:

- `⌘+⌥+1`: Run Bug A scenario (-1)
- `⌘+⌥+2`: Run Bug B scenario (-2)
- `⌘+⌥+r`: Reset workspace
- `⌘+⌥+t`: Run tests
- `⌘+⌥+f`: Run self-evolving fix

## How It Works

1. **Context Reading**: Analyzes workspace files and loads repair memory
2. **Planning**: Uses heuristics and patterns to plan fixes
3. **Patch Application**: Safely applies code changes with guardrails
4. **Testing**: Runs tests to validate fixes
5. **Reflection**: Updates memory with new patterns and heuristics

## Project Structure

```
├── agent/              # Core repair agent components
│   ├── cli.py         # Command-line interface
│   ├── graph.py       # LangGraph workflow definition
│   ├── memory.json    # Learned patterns and heuristics
│   ├── patcher.py     # Safe code modification system
│   ├── planner.py     # Fix planning and generation
│   └── reflect.py     # Pattern learning and memory updates
├── app/               # Target application code
│   └── main.py       # Sample buggy code
├── tests/            # Test suite
└── tools/            # Utility scripts
    └── democtl.py    # Demo scenario manager
```

## Features in Detail

### Heuristic Learning

The system learns from test failures and builds a collection of heuristics for common bugs:
- Off-by-one errors
- None-related TypeError fixes
- Index bounds issues
- Missing key handling
- Import and module errors
- Type mismatches

### Safe Patching

The patcher module includes safety features:
- Restricted to modifying files in `app/` directory
- File count and line change limits
- Path traversal protection
- Diff generation for transparency

### Web-Assisted Fixes

When enabled with Firecrawl:
- Fetches relevant Python documentation
- Uses documentation context for fixes
- Helps with complex issues like None handling

## Contributing

1. Fork the repository
2. Create your feature branch
3. Add tests for new features
4. Submit a pull request

## License

MIT License

## Requirements

- Python 3.8+
- pytest
- langgraph
- weave (optional, for tracking)
- firecrawl-py (optional, for web assistance) 


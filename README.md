# Recut (REimagined Core Utils for Teaching)

This repo contains a reimagining of common posix/linux commands written in Python to:

* Explore how these CLI commands work under the hood
* Explore strengths and weaknesses of Python when implementing these utilities

There will be a Posix In Python blog series based on the work in this repo [here](https://www.mcindi.com/blog).

## Overview

Recut implements classic POSIX utilities in Python to serve as educational resources for understanding CLI command behavior and design patterns. Each implementation prioritizes clarity and learning value over performance.

## Features

- Python implementations of common POSIX commands
- Well-documented source code for learning
- Exploration of Python's strengths and limitations
- Blog articles explaining the implementations

## Installation

Clone the repository:

```bash
git clone https://github.com/McIndi/recut.git
cd recut
```

Install dependencies:

```bash
pip install -e .

# Or for development
pip install -e .[dev]
```

## Running Tests

The project uses several tools for code quality and testing:

```bash
# Format code with Black
black .

# Check code formatting without changes
black --check .

# Security scanning with Bandit
bandit -r .

# Type checking with mypy
mypy .

# Run tests with pytest
pytest

# Run all checks
black --check . && bandit -r . && mypy . && pytest
```

## Usage

Each command can be run as a Python module or script. Refer to individual command documentation for specific usage instructions.

## Available Commands

Currently implemented commands:

- (Coming soon - add your implementations here)

Each command is located in the `src/recut/commands/` directory.

## Blog Series

For detailed explanations of how these commands work, visit the [Posix In Python blog series](https://www.mcindi.com/blog).

## Contributing

Contributions are welcome! Please feel free to submit issues, fork the repository, and create pull requests for any improvements.

## License

MIT

## Author

Cliff

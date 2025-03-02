# Contributing to ER Tool

## Development Setup

1. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On macOS/Linux
```

2. Install development dependencies: 
```bash
pip install -r requirements-dev.txt
```

3. Install pre-commit hooks:
```bash
pre-commit install
```

## Code Style
 - Follow PEP 8
 - Use type hints
 - Write docstrings for functions and classes
 - Keep functions focused and small

 ## Supporting other RDBMS
 ### To add support for another RDBMS, implement the interface defined in the abstract class `db_readers/base.py`

 


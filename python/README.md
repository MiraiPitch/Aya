# Aya

AI Assistant with voice and text interfaces

## Installation

### From PyPI

```bash
pip install aya
```

### From Source

```bash
# Clone the repository
git clone https://github.com/MiraiPitch/Aya/.git
cd aya/python

# Install the package in development mode
pip install -e .
```

## Usage

### Running a File

To run a specific file in the package:

```bash
python -m src.aya.try_liveapi
```

### Command Line Interface

```bash
# Run the CLI version
aya-cli
```

### Graphical User Interface

```bash
# Run the GUI version
aya-gui
```

## Configuration

Aya requires API keys for language models. You can set these in an `.env` file or set environment variables:

1. Copy the example environment file:

    ```bash
    cp .env.example .env
    ```

2. Edit `.env` and add your API keys:

    ```bash
    GOOGLE_API_KEY=your_google_api_key
    ```

## Development

### Setup Development Environment

```bash
pip install -e ".[dev]"
```

### Run Tests

```bash
pytest
```

### Run Linting

Check formatting with Black:

```bash
black --check .
```

Check linting with Flake8:

```bash
flake8 .
```

Check type hints with Mypy:

```bash
mypy .
```

### Build the Package

```bash
python -m build
```

## License

This project is licensed under the MIT License - see the LICENSE file for details.

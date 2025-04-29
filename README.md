# Aya

Aya is a real-time AI assistant that can process audio, video, and text inputs.

## Prerequisites

- Python 3.12 or higher
- A Google Gemini API key
- Conda (recommended for environment management)

## Installation

1. Create and activate a Conda environment:  
```bash
conda create -n aya python=3.12 -y
conda activate aya
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Set your API key in your `.env` file:
```bash
GEMINI_API_KEY=
```



## Usage

Run the Aya live assistant locally:
```bash
python aya_local.py
```

Interaction is possible through voice or text messages

To exit the program, type 'q' as a message

### Available Modes

The script supports different video input modes:

- Audio-only mode (default):
```bash
python aya_local.py --mode none
```

- Camera mode:
```bash
python aya_local.py --mode camera
```

- Screen sharing mode:
```bash
python aya_local.py --mode screen
```


## Remove conda environment

To remove the Conda environment when you're done:
```bash
conda deactivate
conda env remove -n aya
```



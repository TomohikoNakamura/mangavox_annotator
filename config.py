from pathlib import Path

# Define the root path for the frontend static files
FRONT_END_ROOT = Path(__file__).parent / "frontend"
FRONT_END_STATIC_DICT = {
    "full": FRONT_END_ROOT / "full",
    "utt": FRONT_END_ROOT / "utt",
}

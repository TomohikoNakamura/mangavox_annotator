from pathlib import Path

# Define the root path for the frontend static files
FRONT_END_ROOT = Path(__file__).parent / "frontend"
FRONT_END_STATIC_DICT = {
    "full": FRONT_END_ROOT / "full",
    "utt": FRONT_END_ROOT / "utt",
}

# Titles covered by the MangaVox annotation workflow, in UI display order.
MANGA_TITLES = (
    "AkkeraKanjinchou",
    "Akuhamu",
    "EverydayOsakanaChan",
    "HinagikuKenzan",
    "LoveHina_vol01",
    "SaladDays_vol01",
    "TaiyouNiSmash",
    "YasasiiAkuma",
)

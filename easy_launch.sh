#!/bin/bash

set -ue

HOST="127.0.0.1"
PORT="8000"
MANGA109_IMAGES_ROOT="data/manga109/Manga109_released_2023_12_07/images"
MANGA109_XML_ROOT="data/workspace"
MANGA109_XML_SUFFIX="_v1"
MANGAVOX_VOICE_ROOT="data/manga2voice/voices"
MANGAVOX_CONCATENATED_VOICE_ROOT="data/manga2voice/concatenated_voices"

# Manga titles do not contain whitespace, so this also works with macOS Bash 3.2.
MANGA_TITLE_LIST=($(uv run python -c "from config import MANGA_TITLES; print(*MANGA_TITLES)"))

mode=$1
if [ "$mode" != "full" ] && [ "$mode" != "utt" ]; then
    echo "Usage: $0 <mode> <manga_number>"
    echo "mode: full or utt"
    echo "manga_number: 1-${#MANGA_TITLE_LIST[@]}"
    exit 1
fi
num=$2
if ! [[ "$num" =~ ^[0-9]+$ ]] || [ "$num" -lt 1 ] || [ "$num" -gt "${#MANGA_TITLE_LIST[@]}" ]; then
    echo "Invalid manga_number: $num"
    exit 1
fi

num=$((num-1))
MANGA_TITLE=${MANGA_TITLE_LIST[$num]}
echo "Launching MangaVox annotator: ${MANGA_TITLE} in mode: ${mode}"
if [ "$mode" == "full" ]; then
    uv run python launch.py $mode --host "${HOST}" --port ${PORT} \
        --image_root ${MANGA109_IMAGES_ROOT}/${MANGA_TITLE} \
        ${MANGA109_XML_ROOT}/${MANGA_TITLE}${MANGA109_XML_SUFFIX}.xml \
        ${MANGAVOX_VOICE_ROOT}/${MANGA_TITLE}_ALL.flac
elif [ "$mode" == "utt" ]; then
    uv run python launch.py $mode --host "${HOST}" --port ${PORT} \
        --image_root ${MANGA109_IMAGES_ROOT}/${MANGA_TITLE} \
        ${MANGA109_XML_ROOT}/${MANGA_TITLE}${MANGA109_XML_SUFFIX}.xml 
        ${MANGAVOX_CONCATENATED_VOICE_ROOT}/${MANGA_TITLE}
else
    echo "Invalid mode: $mode"
    exit 1
fi
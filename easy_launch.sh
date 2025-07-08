#!/bin/bash

set -ue

MANGA109_IMAGES_ROOT="data/manga109/Manga109_released_2023_12_07/images"
MANGA109_XML_ROOT="data/workspace"
MANGAVOX_VOICE_ROOT="data/manga2voice/voices"
MANGAVOX_CONCATENATED_VOICE_ROOT="data/manga2voice/concatenated_voices"

MANGA_TITLE_LIST=(AkkeraKanjinchou Akuhamu EverydayOsakanaChan HinagikuKenzan LoveHina_vol01 SaladDays_vol01 TaiyouNiSmash YasasiiAkuma)

mode=$1
if [ "$mode" != "full" ] && [ "$mode" != "utt" ]; then
    echo "Usage: $0 <mode> <manga_number>"
    echo "mode: full or utt"
    echo "manga_number: 1-8 (1 for AkkeraKanjinchou, 2 for Akuhamu, ..., 8 for YasasiiAkuma)"
    exit 1
fi
num=$2
if [ $num -gt 8 ]; then
    echo "Invalid argument"
    exit 1
fi

num=$((num-1))
MANGA_TITLE=${MANGA_TITLE_LIST[$num]}
echo "Launching visualizer for manga: ${MANGA_TITLE} in mode: ${mode}"
if [ "$mode" == "full" ]; then
    uv run python launch.py $mode --image_root ${MANGA109_IMAGES_ROOT}/${MANGA_TITLE} ${MANGA109_XML_ROOT}/${MANGA_TITLE}_revised_v5.xml ${MANGAVOX_VOICE_ROOT}/${MANGA_TITLE}_ALL.mp3
elif [ "$mode" == "utt" ]; then
    uv run python launch.py $mode --image_root ${MANGA109_IMAGES_ROOT}/${MANGA_TITLE} ${MANGA109_XML_ROOT}/${MANGA_TITLE}_revised_v5.xml ${MANGAVOX_CONCATENATED_VOICE_ROOT}/${MANGA_TITLE}
else
    echo "Invalid mode: $mode"
    exit 1
fi
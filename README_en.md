# MangaVox Annotation Tool

<p align="center">
  <img
    src="./docs/logo.svg"
    alt="MangaVox Annotation Tool"
    width="75%"
  >
</p>

<p align="center">
  <strong>Edit MangaVox voice annotations and align utterances with Manga109 page elements.</strong>
</p>

<p align="center">
  <a href="./README.md">日本語</a>
  ·
  <strong>English</strong>
</p>

<p align="center">
  <a href="https://github.com/TomohikoNakamura/mangavox_annotator/releases">
    <img
      alt="GitHub release"
      src="https://img.shields.io/github/v/release/TomohikoNakamura/mangavox_annotator?sort=semver"
    >
  </a>
  <a href="./LICENSE">
    <img
      alt="MIT License"
      src="https://img.shields.io/badge/license-MIT-blue"
    >
  </a>
  <a href="https://doi.org/10.1109/ICASSP55912.2026.11463396">
    <img
      alt="ICASSP 2026 paper"
      src="https://img.shields.io/badge/paper-ICASSP%202026-red"
    >
  </a>
  <a href="https://huggingface.co/datasets/imprt/mangavox_annotations">
    <img
      alt="MangaVox dataset"
      src="https://img.shields.io/badge/dataset-MangaVox-green"
    >
  </a>
</p>

## Overview

**MangaVox Annotation Tool** is a browser-based annotation tool for editing annotations associated with MangaVox voice data and linking each utterance to elements on Manga109 manga pages.

The tool displays audio waveforms, manga pages, and utterance metadata in a single interface, allowing the following operations to be performed interactively.

### Features

* Edit voice annotations

  * Modify utterance start and end times
  * Edit utterance text
  * Correct character and actor assignments
  * Correct audio file IDs
* Link utterances to manga elements

  * Link `aligned_voice` elements to Manga109 `frame`, `text`, `face`, and `body` elements
  * Link `aligned_voice` elements to manga page indices
* Two audio display modes

  * `full` mode for working with the mixed audio of an entire title
  * `utt` mode for working with individual utterance audio files
* Save and apply edit histories

  * Save edits as YAML change logs
  * Update XML annotations from change logs
  * Generate a list of differences between XML versions

> [!NOTE]
> This repository does not include the MangaVox or Manga109 data.
> Obtain the data from their respective distribution sources and use each dataset in accordance with its terms of use.

## Screenshots

### Full-audio annotation mode (`full` mode)

This mode displays the waveform of the full mixed audio for a title and allows annotations to be edited while selecting utterance regions.

<p align="center">
  <img
    src="./docs/interface_sample_full.jpg"
    alt="Full-audio annotation mode"
    width="95%"
  >
</p>

### Utterance-level annotation mode (`utt` mode)

This mode allows individual annotations to be edited while switching between utterance-level audio files.

<p align="center">
  <img
    src="./docs/interface_sample_utt.jpg"
    alt="Utterance-level annotation mode"
    width="95%"
  >
</p>

## Requirements

* Python 3.12 or later
* [uv](https://docs.astral.sh/uv/)

## Installation

Clone the repository and use uv to create the execution environment.

```bash
git clone https://github.com/TomohikoNakamura/mangavox_annotator.git
cd mangavox_annotator
uv sync
```

## Data Preparation

Running this tool requires Manga109 images and metadata, together with MangaVox audio and metadata.

### 1. Place the Manga109 images and metadata

Place the Manga109 image data for each title in the following directory:

```text
data/manga109/Manga109_released_2023_12_07/images/<manga_title>
```

Place the XML metadata for each title at the following path:

```text
data/manga109/Manga109_released_2023_12_07/annotations/<manga_title>.xml
```

### 2. Place the MangaVox audio data

Place the utterance-level audio files for each title in the following directory:

```text
data/manga2voice/concatenated_voices/<manga_title>
```

To use a different root directory, specify it with the `--audio-root` option of the scripts described below.

### 3. Place the public-format MangaVox XML

Place the public-format MangaVox XML containing `voice` elements at the following path:

```text
data/workspace/<manga_title>.xml
```

For example, for `AkkeraKanjinchou`, use the following path:

```text
data/workspace/AkkeraKanjinchou.xml
```

### 4. Generate the mixed full-length audio

The `full` mode uses a mixed audio file containing all audio tracks for a title.

To process all titles listed in `MANGA_TITLES` in `config.py`, run:

```bash
uv run python -m scripts.mix_mangavox_audio
```

If the input audio is stored in `concatenated_voices_v2`, explicitly specify the input root:

```bash
uv run python -m scripts.mix_mangavox_audio \
  --audio-root data/manga2voice/concatenated_voices_v2 \
  --overwrite
```

The mixed audio is generated at:

```text
data/manga2voice/voices/<manga_title>_ALL.flac
```

The following rules are applied during mixing:

* Files matching `*_Gaya.flac` are treated as crowd or background chatter tracks.
* By default, these tracks are mixed after being attenuated to `-40 dB`.
* For voice ID intervals registered in `GAYA_UTT_GAINS_IN_DB` in `config.py`, the specified gain is applied with a small margin before and after each interval.

### 5. Merge the MangaVox and Manga109 metadata

Merge the public-format MangaVox XML with the Manga109 XML to generate XML for the annotation tool.

To process all titles listed in `MANGA_TITLES` in `config.py`, run:

```bash
uv run python -m scripts.merge_with_manga109_annotations
```

The generated XML file generally follows this naming convention:

```text
data/workspace/<manga_title>_v1.xml
```

To overwrite existing `*_v1.xml` files, specify `--overwrite`:

```bash
uv run python -m scripts.merge_with_manga109_annotations \
  --overwrite
```

To process only selected titles, specify them with `--titles`:

```bash
uv run python -m scripts.merge_with_manga109_annotations \
  --titles AkkeraKanjinchou HinagikuKenzan
```

To directly specify the input and output files for a single title, run:

```bash
MANGA_TITLE="AkkeraKanjinchou"

uv run python -m scripts.merge_with_manga109_annotations \
  "data/workspace/${MANGA_TITLE}.xml" \
  "data/manga109/Manga109_released_2023_12_07/annotations/${MANGA_TITLE}.xml" \
  "data/workspace/${MANGA_TITLE}_v1.xml"
```

## Launching the Annotation Tool

### Using the convenience launch script

Run the following Bash script:

```bash
bash easy_launch.sh <mode> <manga_index>
```

Specify the following arguments:

* `<mode>`

  * `full`: display the mixed audio for the entire title
  * `utt`: display utterance-level audio files
* `<manga_index>`

  * index number of the target title

The current title indices are as follows:

| Index | Title                 |
| ----: | --------------------- |
|     1 | `AkkeraKanjinchou`    |
|     2 | `Akuhamu`             |
|     3 | `EverydayOsakanaChan` |
|     4 | `HinagikuKenzan`      |
|     5 | `LoveHina_vol01`      |
|     6 | `SaladDays_vol01`     |
|     7 | `TaiyouNiSmash`       |
|     8 | `YasasiiAkuma`        |

For example, to launch `AkkeraKanjinchou` in `full` mode, run:

```bash
bash easy_launch.sh full 1
```

### Running the command directly

The basic command format is:

```bash
uv run python launch.py \
  <mode> \
  --image_root <image_root> \
  <xml_path> \
  <audio_path>
```

The arguments are described below.

| Argument       | Description                                                    |
| -------------- | -------------------------------------------------------------- |
| `<mode>`       | `full` or `utt`                                                |
| `--image_root` | Directory containing the Manga109 manga images                 |
| `<xml_path>`   | XML file used by the annotation tool                           |
| `<audio_path>` | Audio file or directory containing utterance-level audio files |

The required form of `<audio_path>` depends on the selected mode.

* `full` mode

  * Mixed audio file for the entire title
  * Example: `data/manga2voice/voices/AkkeraKanjinchou_ALL.flac`
* `utt` mode

  * Directory containing utterance-level audio files
  * Example: `data/manga2voice/concatenated_voices/AkkeraKanjinchou`

#### Example for `full` mode

```bash
MANGA_TITLE="AkkeraKanjinchou"

uv run python launch.py \
  full \
  --image_root "data/manga109/Manga109_released_2023_12_07/images/${MANGA_TITLE}" \
  "data/workspace/${MANGA_TITLE}_v1.xml" \
  "data/manga2voice/voices/${MANGA_TITLE}_ALL.flac"
```

#### Example for `utt` mode

```bash
MANGA_TITLE="AkkeraKanjinchou"

uv run python launch.py \
  utt \
  --image_root "data/manga109/Manga109_released_2023_12_07/images/${MANGA_TITLE}" \
  "data/workspace/${MANGA_TITLE}_v1.xml" \
  "data/manga2voice/concatenated_voices/${MANGA_TITLE}"
```

### Accessing the tool in a browser

After starting the server, open the following URL in a web browser:

```text
http://localhost:8000
```

Annotation changes are saved as logs in the following directory:

```text
logs/<mode>/<manga_title>
```

The standard change log file is:

```text
logs/<mode>/<manga_title>/change_log.yaml
```

## Using the Annotation Tool

### Keyboard and mouse controls

| Input                 | Action                                                                                           |
| --------------------- | ------------------------------------------------------------------------------------------------ |
| `Space`               | Toggle audio playback and pause                                                                  |
| `n`                   | Select the next region                                                                           |
| `b`                   | Select the previous region                                                                       |
| `s`                   | Save changes to the selected region                                                              |
| `h`                   | Show or hide the help panel                                                                      |
| Mouse wheel           | Zoom the waveform in or out                                                                      |
| Click the waveform    | Clear the current region selection                                                               |
| Click a region        | Select the clicked region                                                                        |
| Click the manga image | Select the smallest bounding box containing the clicked position and link it to the audio region |

### Interface layout

#### 1. Waveform panel

* Displays the audio waveform and utterance regions.
* Allows utterance regions to be selected using the keyboard or mouse.
* Provides a zoom slider for adjusting the waveform display resolution.

#### 2. Manga image panel

* Displays Manga109 manga pages.
* Overlays the bounding boxes of `frame`, `text`, `face`, and `body` elements.
* Links a bounding box to the selected audio region when the box is clicked.

#### 3. Annotation panel

* Displays the metadata associated with the selected utterance region.
* Allows utterance times, text, character, actor, audio file ID, and related values to be edited.
* Provides controls for saving or resetting edits.

### Basic annotation workflow

1. Load the manga images, XML annotations, and audio data.
2. Select the target utterance by clicking a region in the waveform or by pressing `n` or `b`.
3. Edit the utterance start time, end time, text, character, actor, or other values as necessary.
4. Click a bounding box on the manga image to link the utterance to a manga element.
5. Save the changes by pressing `s` or clicking the save button.
6. The edits are recorded in the following change log:

```text
logs/<mode>/<manga_title>/change_log.yaml
```

## Updating XML from Change Logs

Edits made in the annotation tool are not written directly to the original XML. After annotation is complete, use the change log to generate a new XML file.

### Update the XML

```bash
MODE="full"  # or "utt"
MANGA_TITLE="AkkeraKanjinchou"

uv run python -m scripts.update_mangavox_annotations \
  --change_log_dir "logs/${MODE}" \
  "data/workspace/${MANGA_TITLE}_v1.xml" \
  "data/workspace/${MANGA_TITLE}_v2.xml"
```

This example generates the updated `*_v2.xml` file from the original `*_v1.xml` file.

### Generate a list of changes

Optionally, compare the XML files before and after the update and export the changes in YAML format.

```bash
MANGA_TITLE="AkkeraKanjinchou"

uv run python -m scripts.create_change_list \
  "data/workspace/${MANGA_TITLE}_v1.xml" \
  "data/workspace/${MANGA_TITLE}_v2.xml" \
  "data/workspace/${MANGA_TITLE}/change_log_v2-v1.yaml"
```

## Generating Statistics

To regenerate the statistical tables in the Appendix, run:

```bash
uv run python -m scripts.generate_annotation_stats \
  data/workspace/*_v2.xml \
  --audio-root data/manga2voice/concatenated_voices
```

## Citation

When using this tool in research, cite the following paper:

```bibtex
@inproceedings{STakamichi2026ICASSP,
    author = "Takamichi, Shinnosuke and Nakamura, Tomohiko and Suda, Hitoshi and Fukayama, Satoru and Ogata, Jun",
    booktitle = "Proceedings of IEEE International Conference on Acoustics, Speech, and Signal Processing (ICASSP)",
    title = "MangaVox: {Dataset} of acted voices aligned with manga images towards computer understanding of audio comics",
    pages = "19467--19471",
    month = "May",
    year = "2026",
    doi = "10.1109/ICASSP55912.2026.11463396"
}
```

## License

The source code of this tool is provided under the [MIT License](./LICENSE).

The MangaVox and Manga109 data are governed by terms of use that are separate from the license of this tool.

* Use the MangaVox audio and metadata in accordance with the MangaVox terms of use.
* Use the Manga109 images and metadata in accordance with the Manga109 terms of use.
* The MIT License of this repository does not apply to the MangaVox or Manga109 data.

# Appendix
## Main Attributes of Utterance Elements

The following table lists the main attributes used in `voice` and `aligned_voice` elements.

| Attribute       | Description                                      | Required | Example          |
| :-------------- | :----------------------------------------------- | :------: | :--------------- |
| `id`            | Unique utterance ID                              |     ✓    | `60000027`       |
| `index`         | Utterance order index                            |     ✓    | `38`             |
| `start`         | Utterance start time [s]                         |     ✓    | `161.095`        |
| `end`           | Utterance end time [s]                           |     ✓    | `161.635`        |
| `episode_index` | Episode index within the title                   |     ✓    | `1`              |
| `page_index`    | Page index                                       |     ✓    | `4`              |
| `actor_id`      | Actor ID                                         |     ✓    | `08F20`          |
| `character_id`  | Character ID                                     |     ✓    | `00001d7b`       |
| `audio_id`      | Audio file ID                                    |     ✓    | `08F20_Sakisuke` |
| `text_id`       | ID of the corresponding Manga109 `text` element  |          | `00001d93`       |
| `frame_id`      | ID of the corresponding Manga109 `frame` element |          | `00001d96`       |
| `face_id`       | ID of the corresponding Manga109 `face` element  |          | `00001dc2`       |
| `body_id`       | ID of the corresponding Manga109 `body` element  |          | `00001d94`       |

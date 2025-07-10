import io
import json
from dataclasses import asdict
from pathlib import Path
from typing import Dict, List, Optional

import yaml
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, Response, StreamingResponse

from annotator_api.utils import (
    AppState,
    Constants,
    PreLoadedData,
    generate_client_uid,
    json_to_hash,
)
from mangavox_api.utils import get_timestamp_in_iso8601_format

router = APIRouter()


@router.get("/stats")
async def get_stats(request: Request) -> Dict[str, Optional[int | str]]:
    """Get statistics about the manga, including title, total pages, and total voices.

    Args:
        request (Request): The FastAPI request object.

    Returns:
        Dict[str, Optional[int | str]]: A dictionary containing the title, total pages, total voices, start page, end page, and a unique client ID.
    """
    state: AppState = request.app.state.app_data
    if state.pre_loaded_data is None or state.constants is None:
        raise HTTPException(
            status_code=500,
            detail="Application state not initialized. Please check the server logs.",
        )
    preloaded_data: PreLoadedData = state.pre_loaded_data
    constants: Constants = state.constants
    # Check if the pre-loaded data and constants are initialized
    if preloaded_data.aligned_voices is None:
        raise HTTPException(
            status_code=500,
            detail="Annotation data not loaded. Please check the server logs.",
        )
    if (
        not isinstance(constants.PAGE_RANGE, (list, tuple))
        or len(constants.PAGE_RANGE) != 2
    ):
        raise HTTPException(
            status_code=500,
            detail="PAGE_RANGE is not properly initialized.",
        )

    uid = generate_client_uid(request)

    # Get title, total pages, and total voices
    title = preloaded_data.aligned_voices.title
    start_page = constants.PAGE_RANGE[0]
    end_page = constants.PAGE_RANGE[1]
    total_pages = end_page - start_page + 1
    total_voices = len(getattr(preloaded_data.aligned_voices, "voices", []))

    return {
        "title": title,
        "total_pages": total_pages,
        "total_voices": total_voices,
        "start_page": start_page,
        "end_page": end_page,
        "uid": uid,
    }


@router.get("/actors")
async def get_actors(request: Request) -> List[str]:
    """Get a list of unique actors from the aligned voices data.

    Args:
        request (Request): The FastAPI request object.

    Returns:
        List[str]: A sorted list of unique actor IDs.
    """
    state: AppState = request.app.state.app_data
    if state.pre_loaded_data is None:
        raise HTTPException(
            status_code=500,
            detail="Application state not initialized. Please check the server logs.",
        )
    if state.pre_loaded_data.aligned_voices is None:
        raise HTTPException(
            status_code=500,
            detail="Annotation data not loaded. Please check the server logs.",
        )
    actor_list = []
    for voice in state.pre_loaded_data.aligned_voices.voices:
        if voice.actor_id is not None:
            actor_list.append(voice.actor_id)
    return sorted(list(set(actor_list)))


@router.get("/audio_characters")
async def get_audio_characters(request: Request) -> List[str]:
    """ "Get a list of characters for which audio data is available.

    Returns:
        List[str]: A sorted list of character names.
    """
    state: AppState = request.app.state.app_data
    if state.pre_loaded_data is None:
        raise HTTPException(
            status_code=500,
            detail="Application state not initialized. Please check the server logs.",
        )
    if state.pre_loaded_data.audio_raw_data_dict is None:
        raise HTTPException(
            status_code=500,
            detail="Audio data not loaded. Please check the server logs.",
        )

    return sorted(list(state.pre_loaded_data.audio_raw_data_dict.keys()))


@router.get("/image/{page_number}")
async def get_image(page_number: int, request: Request) -> StreamingResponse:
    """Get the image data for a specific page number.

    Args:
        page_number (int): The page number for which to retrieve the image data.

    Returns:
        StreamingResponse: A streaming response containing the image data in JPEG format.
    """
    state: AppState = request.app.state.app_data
    if state.pre_loaded_data is None or state.constants is None:
        raise HTTPException(
            status_code=500,
            detail="Application state not initialized. Please check the server logs.",
        )
    preloaded_data: PreLoadedData = state.pre_loaded_data
    constants: Constants = state.constants
    if not (constants.PAGE_RANGE[0] <= page_number <= constants.PAGE_RANGE[1]):
        raise HTTPException(status_code=404, detail="Page not found")

    image_data = preloaded_data.image_data[page_number - constants.PAGE_RANGE[0]]

    headers = {
        "Content-Type": "image/jpeg",  # MIME type
        "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",  # Disable caching
        "Pragma": "no-cache",
        "Expires": "0",
    }
    return StreamingResponse(
        io.BytesIO(image_data), media_type="image/jpeg", headers=headers
    )


@router.get("/annotations/image/{page_number}")
async def get_image_annotations(
    page_number: int, request: Request
) -> StreamingResponse:
    """Get the image annotations for a specific page number.

    Args:
        page_number (int): The page number for which to retrieve the image annotations.

    Returns:
        StreamingResponse: A streaming response containing the image annotations in JSON format.
    """
    state: AppState = request.app.state.app_data
    if state.pre_loaded_data is None:
        raise HTTPException(
            status_code=500,
            detail="Application state not initialized. Please check the server logs.",
        )
    if state.pre_loaded_data.aligned_voices is None:
        raise HTTPException(
            status_code=500,
            detail="Annotation data not loaded. Please check the server logs.",
        )

    def convert_annotation_to_json(aligned_voices):
        ret = []
        if page_number < 0:  # Get annotations for all pages
            for page in aligned_voices.pages.page:
                page_json = asdict(page)
                ret.append(page_json)
        else:
            for page in aligned_voices.pages.page:
                if page.index == page_number:
                    page_json = asdict(page)
                    ret = page_json
                    break
        ret = json.dumps(ret, ensure_ascii=False)
        for i in range(0, len(ret), 4096):
            yield ret[i : i + 4096]

    header = {
        "Content-Type": "application/json",
        "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",  # Disable caching
        "Pragma": "no-cache",
        "Expires": "0",
    }
    return StreamingResponse(
        convert_annotation_to_json(state.pre_loaded_data.aligned_voices),
        media_type="application/json",
        headers=header,
    )


@router.get("/annotations/voice/{voice_id}")
async def get_voice_annotations(
    voice_id: str, request: Request, block_size: int = 4096
) -> StreamingResponse:
    """Get the annotations for a specific voice ID.

    Args:
        voice_id (str): The ID of the voice for which to retrieve annotations.
        block_size (int): The size of each block of data to yield in the streaming response.

    Returns:
        StreamingResponse: A streaming response containing the voice annotations in JSON format.
    """
    state: AppState = request.app.state.app_data
    if state.pre_loaded_data is None:
        raise HTTPException(
            status_code=500,
            detail="Application state not initialized. Please check the server logs.",
        )
    if state.pre_loaded_data.aligned_voices is None:
        raise HTTPException(
            status_code=500,
            detail="Annotation data not loaded. Please check the server logs.",
        )

    def convert_annotation_to_json(aligned_voices):
        ret = []
        if voice_id == "all":
            for aligned_voice in aligned_voices.voices:
                voice_json = asdict(aligned_voice)
                voice_json["server_side_hash"] = json_to_hash(voice_json)
                voice_json["character_name"] = (
                    aligned_voices.characters.get_character_name_by_id(
                        aligned_voice.character_id
                    )
                )
                ret.append(voice_json)
        else:
            for aligned_voice in aligned_voices.voices:
                if aligned_voice.id == voice_id:
                    voice_json = asdict(aligned_voice)
                    voice_json["server_side_hash"] = json_to_hash(voice_json)
                    voice_json["character_name"] = (
                        aligned_voices.characters.get_character_name_by_id(
                            aligned_voice.character_id
                        )
                    )
                    ret = voice_json
                    break
        ret = json.dumps(ret, ensure_ascii=False)
        for i in range(0, len(ret), block_size):
            yield ret[i : i + block_size]

    header = {
        "Content-Type": "application/json",
        "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",  # Disable caching
        "Pragma": "no-cache",
        "Expires": "0",
    }
    return StreamingResponse(
        convert_annotation_to_json(state.pre_loaded_data.aligned_voices),
        media_type="application/json",
        headers=header,
    )


@router.get("/annotations/characters")
async def get_characters(request: Request) -> StreamingResponse:
    """Get a list of characters from the aligned voices data.

    Returns:
        StreamingResponse: A streaming response containing the character data in JSON format.
    """
    state: AppState = request.app.state.app_data
    if state.pre_loaded_data is None:
        raise HTTPException(
            status_code=500,
            detail="Application state not initialized. Please check the server logs.",
        )
    if state.pre_loaded_data.aligned_voices is None:
        return {"error": "Annotation data not loaded. Please check the server logs."}

    def convert_annotation_to_json(aligned_voices):
        ret = []
        for character in aligned_voices.characters.character:
            character_json = {
                "id": character.id,
                "name": f"{character.name} ({character.id})",
            }
            ret.append(character_json)
        ret = json.dumps(ret, ensure_ascii=False)
        for i in range(0, len(ret), 4096):
            yield ret[i : i + 4096]

    header = {
        "Content-Type": "application/json",
        "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",  # Disable caching
        "Pragma": "no-cache",
        "Expires": "0",
    }
    return StreamingResponse(
        convert_annotation_to_json(state.pre_loaded_data.aligned_voices),
        media_type="application/json",
        headers=header,
    )


@router.post("/update/annotation")
async def update_annotation(annotation: dict, request: Request) -> Response:
    """Update an annotation in the aligned voices data.

    Args:
        annotation (dict): The annotation data to update, including the voice ID, character name,
                           and other fields to update.

    Returns:
        Dict[str, str]: A dictionary containing the status of the update operation.
    """
    state: AppState = request.app.state.app_data
    if (
        state.pre_loaded_data is None
        or state.constants is None
        or state.output_data is None
    ):
        raise HTTPException(
            status_code=500,
            detail="Application state not initialized. Please check the server logs.",
        )
    if state.pre_loaded_data.aligned_voices is None:
        raise HTTPException(
            status_code=500,
            detail="Annotation data not loaded. Please check the server logs.",
        )
    if state.output_data.change_log_lock is None:
        raise HTTPException(
            status_code=500,
            detail="Change log lock not initialized. Please check the server logs.",
        )

    async with state.output_data.change_log_lock:
        annotation.pop("character_name", None)  # Delete character_name if it exists
        try:
            uid = annotation.pop("uid")
        except KeyError:
            raise HTTPException(
                status_code=400,
                detail="UID is required in the annotation data.",
            )

        # Get the index of the element whose id matches
        target_indexes = []
        for i, voice in enumerate(state.pre_loaded_data.aligned_voices.voices):
            if voice.id == annotation["id"]:
                target_indexes.append(i)
        if len(target_indexes) != 1:
            raise HTTPException(
                status_code=404,
                detail="Annotation ID not found.",
            )
        target_index = target_indexes[0]

        # Check server side hash
        server_side_hash = annotation.pop("server_side_hash")
        if server_side_hash != json_to_hash(
            asdict(state.pre_loaded_data.aligned_voices.voices[target_index])
        ):
            raise HTTPException(
                status_code=400,
                detail="Server side hash does not match. Please refresh the page.",
            )

        # Check if the update is required
        ret = {
            "timestamp": get_timestamp_in_iso8601_format(),
            "uid": uid,
            "voice_id": annotation["id"],
            "change": [],
        }
        change_logs = state.pre_loaded_data.aligned_voices.voices[target_index].update(
            annotation, verbose=True
        )
        ret["change"] = change_logs
        is_changed = len(change_logs) > 0

        if is_changed:
            # If the annotation is changed, update the assignment to the image-based elements
            state.pre_loaded_data.aligned_voices.update_assigned(
                page_index=annotation["page_index"]
            )
        else:
            # If no change is made, return 204 No Content
            return Response(status_code=204)

        # Save the change log
        with open(state.output_data.change_log_filename, "a") as fp:
            fp.write(yaml.dump([ret], allow_unicode=True))

    return Response(status_code=200)


@router.get("/", response_class=HTMLResponse)
async def root(request: Request) -> HTMLResponse:
    static_dir: Path = request.app.state.static_dir
    html_file = static_dir / "index.html"
    return HTMLResponse(content=html_file.read_text(), status_code=200)


@router.get("/favicon.ico", include_in_schema=False)
async def favicon(request: Request):
    static_dir: Path = request.app.state.static_dir
    return FileResponse(static_dir / "favicon.png")

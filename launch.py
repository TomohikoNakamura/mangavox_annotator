import argparse
from contextlib import asynccontextmanager
from pathlib import Path

from annotator_api.common_router import router as common_router
from annotator_api.full_router import pre_init as full_pre_init
from annotator_api.full_router import router as full_router
from annotator_api.utils import AppState
from annotator_api.utt_router import pre_init as utt_pre_init
from annotator_api.utt_router import router as utt_router
# from annotator_api.utt_router import validate_before_start
from config import FRONT_END_STATIC_DICT
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from loguru import logger


def create_app(args: argparse.Namespace) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        logger.info("Starting MangaVox Annotation Tool server...")
        app.state.app_data = AppState(None, None, None)
        if args.command == "full":
            app.state.app_data = full_pre_init(args)
        elif args.command == "utt":
            app.state.app_data = utt_pre_init(args)
            # validate_before_start(
            #     app.state.app_data.pre_loaded_data, app.state.app_data.output_data
            # )
        else:
            raise ValueError(
                f"Unknown command: {args.command}. Expected 'full' or 'utterance'."
            )

        if app.state.app_data.pre_loaded_data is None:
            logger.error("Pre-loaded data is not initialized. Exiting.")
            raise RuntimeError("Pre-loaded data is not initialized.")
        if app.state.app_data.constants is None:
            logger.error("Constants are not initialized. Exiting.")
            raise RuntimeError("Constants are not initialized.")
        if app.state.app_data.output_data is None:
            logger.error("Output data is not initialized. Exiting.")
            raise RuntimeError("Output data is not initialized.")

        # Run the server
        yield

        # Shutdown logic
        logger.info("Shutting down MangaVox Annotation Tool server...")
        if app.state.app_data.output_data.change_log_filename is not None:
            # remove change log file if it is empty
            if not app.state.app_data.output_data.change_log_filename.exists():
                (
                    app.state.app_data.output_data.change_log_filename.parent
                    / "config.yaml"
                ).unlink()
                app.state.app_data.output_data.change_log_filename.parent.rmdir()

    # Set up the FastAPI app
    app = FastAPI(lifespan=lifespan)
    app.include_router(common_router)
    if args.command == "full":
        app.include_router(full_router)
    elif args.command == "utt":
        app.include_router(utt_router)
    else:
        raise ValueError(
            f"Unknown command: {args.command}. Expected 'full' or 'utterance'."
        )
    # Add CORS middleware to allow requests from the frontend
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:8000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    # Directory settings for static files
    app.state.static_dir = FRONT_END_STATIC_DICT.get(args.command)
    app.mount("/static", StaticFiles(directory=app.state.static_dir), name="static")

    return app


#####
def parse_args():
    common_parser = argparse.ArgumentParser(
        description="MangaVox Annotation Tool Server",
        add_help=False,
    )
    common_parser.add_argument(
        "--image_root", type=Path, required=True, help="Root directory of the images."
    )
    common_parser.add_argument(
        "aligned_voices_filename",
        type=Path,
        help="Path to the aligned voices XML file.",
    )

    parser = argparse.ArgumentParser(description="MangaVox Annotation Tool Server")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Subparser for the full command
    full_parser = subparsers.add_parser(
        "full",
        parents=[common_parser],
        help="Launch the MangaVox Annotation Tool server for the entire audio",
    )
    full_parser.add_argument(
        "--change_log_dir",
        type=Path,
        default="logs/full",
        help="Directory to save change logs.",
    )
    full_parser.add_argument(
        "audio_filename", type=Path, help="Path to the audio (mp3) file."
    )

    # Subparser for the utterance command
    utterance_parser = subparsers.add_parser(
        "utt",
        parents=[common_parser],
        help="Launch the MangaVox Annotation Tool server for utterance-level audio",
    )
    utterance_parser.add_argument(
        "--change_log_dir",
        type=Path,
        default="logs/utt",
        help="Directory to save change logs.",
    )
    utterance_parser.add_argument(
        "audio_dir", type=Path, help="Path to the audio directory."
    )

    args = parser.parse_args()
    return args


if __name__ == "__main__":
    import uvicorn

    args = parse_args()
    app = create_app(args)
    uvicorn.run(app, host="0.0.0.0", port=8000)

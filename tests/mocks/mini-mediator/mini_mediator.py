import argparse
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

load_dotenv()
IP = os.environ.get("MINI_MEDIATOR_IP", "localhost")
PORT = int(os.environ.get("MINI_MEDIATOR_PORT", 11998))
MODULE_PATH = "mini_mediator:app"

app = FastAPI(title="Mini-Mediator Mock Server")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/v1/models")
async def get_models() -> JSONResponse:
    models = {
        "data": [
            {
                "id": "mini-mediator",
                "object": "model",
                "created": 12345,
                "owned_by": "localhost",
            },
            {
                "id": "mini-mediator:thinking",
                "object": "model",
                "created": 123456,
                "owned_by": "localhost",
            },
        ],
    }
    return JSONResponse(content=models)


@app.post("/v1/chat/completions")
async def chat_completions(request: Request) -> JSONResponse:
    req_data = await request.json()
    model_id = req_data.get("model", "mini-mediator")
    pretty_json = json.dumps(req_data, indent=2)

    response_dict = {
        "id": "chatcmpl-m1n1M3d14t0r",
        "object": "chat.completion",
        "created": 246810,
        "model": model_id,
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": f"Received request with data:\n```json\n{pretty_json}\n```",
                    "refusal": None,
                    "annotations": [],
                },
                "logprobs": None,
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": 42,
            "completion_tokens": 42,
            "total_tokens": 84,
            "prompt_tokens_details": {
                "cached_tokens": 0,
                "audio_tokens": 0,
            },
            "completion_tokens_details": {
                "reasoning_tokens": 0,
                "audio_tokens": 0,
                "accepted_prediction_tokens": 0,
                "rejected_prediction_tokens": 0,
            },
        },
    }

    return JSONResponse(content=response_dict)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Mini-Mediator mock server")
    parser.add_argument(
        "--reload",
        action="store_true",
        help="Enable FastAPI auto-reload (development only)",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    print(f"Starting Mini-Mediator on {IP}:{PORT} (reload={args.reload})", flush=True)
    target = MODULE_PATH if args.reload else app
    reload_dirs = [str(SCRIPT_DIR)] if args.reload else None
    uvicorn.run(
        target,
        host=IP,
        port=PORT,
        reload=args.reload,
        reload_dirs=reload_dirs,
        log_level="info",
    )
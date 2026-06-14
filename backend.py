import asyncio
import sys
import subprocess
import os
import json
import traceback
from typing import List, Optional
from dotenv import load_dotenv
import httpx
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

load_dotenv()

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
async def root():
    return FileResponse("static/index.html")


@app.get("/api/files")
async def list_files():
    folder = os.getenv("FOLDER", "./html_reports")
    if not os.path.exists(folder):
        return {"files": []}
    files = [f for f in os.listdir(folder) if f.endswith(".html")]
    return {"files": sorted(files)}


@app.get("/api/cache")
async def get_cache():
    cache_path = os.getenv("CACHE_FILE", "parsed_messages.json")
    if not os.path.exists(cache_path):
        return {"exists": False, "data": None}
    with open(cache_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return {"exists": True, "data": data}


class ModelsRequest(BaseModel):
    api_key: str


@app.get("/api/has_key")
async def has_key():
    key = os.getenv("OPENROUTER_API_KEY")
    return {"has_key": bool(key) and key.strip() != "" and key != "sk-or-v1-..."}


@app.get("/api/env_keys")
async def get_env_keys():
    """Возвращает список ключей из переменных окружения OPENROUTER_API_KEYS (через запятую) или OPENROUTER_API_KEY."""
    keys_str = os.getenv("OPENROUTER_API_KEYS", "")
    if not keys_str:
        keys_str = os.getenv("OPENROUTER_API_KEY", "")
    if not keys_str:
        return {"keys": []}
    # разделитель – запятая, можно также поддерживать пробелы
    keys = [k.strip() for k in keys_str.split(",") if k.strip()]
    return {"keys": keys}


def get_api_key(request_key: str = None) -> str:
    key = request_key or os.getenv("OPENROUTER_API_KEY")
    if not key or key.strip() == "" or key == "sk-or-v1-...":
        raise HTTPException(status_code=400, detail="API key is missing or invalid")
    return key


@app.post("/api/models")
async def get_models(req: ModelsRequest):
    try:
        api_key = get_api_key(req.api_key)
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                "https://openrouter.ai/api/v1/models",
                headers={"Authorization": f"Bearer {api_key}"},
            )
            if response.status_code != 200:
                raise HTTPException(
                    status_code=response.status_code, detail="Failed to fetch models"
                )
            data = response.json()
            models = []
            for m in data.get("data", []):
                if m.get("id") and m.get("context_length", 0) > 0:
                    models.append(
                        {
                            "id": m["id"],
                            "name": m.get("name", m["id"]),
                            "context_length": m.get("context_length"),
                            "pricing": m.get("pricing", {}),
                        }
                    )
            return {"models": models}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class RunRequest(BaseModel):
    api_keys: List[str]   # список ключей
    model: str            # одна модель
    max_workers: int = 5
    max_retries: int = 10
    force: bool = False
    folder: Optional[str] = None
    cache_file: Optional[str] = None
    output_csv: Optional[str] = None


@app.websocket("/ws/run")
async def websocket_run(websocket: WebSocket):
    await websocket.accept()
    process = None
    try:
        data = await websocket.receive_json()
        req = RunRequest(**data)

        if not req.api_keys:
            await websocket.send_json({"type": "error", "message": "No API keys provided"})
            return

        folder = req.folder or os.getenv("FOLDER", "./html_reports")
        cache_file = req.cache_file or os.getenv("CACHE_FILE", "parsed_messages.json")
        output_csv = req.output_csv or os.getenv("OUTPUT_CSV", "dangerous_openrouter.csv")

        python_exe = sys.executable
        cmd = [
            python_exe,
            "-u",
            "check.py",
            "--folder", folder,
            "--cache", cache_file,
            "--output", output_csv,
            "--api-keys", ",".join(req.api_keys),
            "--model", req.model,
            "--max-workers", str(req.max_workers),
            "--max-retries", str(req.max_retries),
        ]
        if req.force:
            cmd.append("--force")

        await websocket.send_json({"type": "stdout", "line": f"Команда: {' '.join(cmd)}"})
        print(f"Запуск команды: {' '.join(cmd)}")

        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=os.getcwd(),
            text=True,
            bufsize=1,
            encoding="utf-8",
        )

        loop = asyncio.get_running_loop()

        async def safe_send(payload):
            try:
                await websocket.send_json(payload)
                return True
            except WebSocketDisconnect:
                return False
            except Exception:
                return False

        async def read_stdout():
            try:
                while True:
                    line = await loop.run_in_executor(None, process.stdout.readline)
                    if not line:
                        break
                    if not await safe_send({"type": "stdout", "line": line.rstrip()}):
                        break
            except Exception as e:
                await safe_send({"type": "error", "message": f"Ошибка чтения stdout: {str(e)}"})

        async def read_stderr():
            try:
                while True:
                    line = await loop.run_in_executor(None, process.stderr.readline)
                    if not line:
                        break
                    if not await safe_send({"type": "stderr", "line": line.rstrip()}):
                        break
            except Exception as e:
                await safe_send({"type": "error", "message": f"Ошибка чтения stderr: {str(e)}"})

        async def receive_client():
            try:
                while True:
                    msg = await websocket.receive_json()
                    if msg.get("type") == "abort":
                        if process and process.poll() is None:
                            process.terminate()
                            await safe_send({"type": "stdout", "line": "Процесс остановлен пользователем."})
            except WebSocketDisconnect:
                pass
            except Exception as e:
                await safe_send({"type": "error", "message": f"Ошибка получения управления: {str(e)}"})

        tasks = [
            asyncio.create_task(read_stdout()),
            asyncio.create_task(read_stderr()),
            asyncio.create_task(receive_client()),
        ]
        done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        for task in pending:
            task.cancel()

        if process:
            return_code = process.wait()
        else:
            return_code = -1
        await safe_send({"type": "exit", "code": return_code})

    except WebSocketDisconnect:
        print("Client disconnected")
        if process:
            process.terminate()
    except Exception as e:
        error_details = traceback.format_exc()
        print(error_details)
        await websocket.send_json({"type": "error", "message": f"Ошибка сервера: {str(e)}\n{error_details}"})
    finally:
        if process:
            process.stdout.close()
            process.stderr.close()
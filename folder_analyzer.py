from fastapi import FastAPI, HTTPException,Query
from pydantic import BaseModel
import os
from collections import defaultdict
from fastapi.responses import StreamingResponse
import io
import csv
import asyncio

app = FastAPI(
    title="Folder Analyzer API",
    description="Analyze folders and export file statistics",
    redoc_url=None,
    version="1.0.0"
)


class FolderRequest(BaseModel):
    path:str='/home'
def human_size(bytes_size: int) -> str:
    for unit in ["B", "KB", "MB", "GB", "TB", "PB"]:
        if bytes_size < 1024:
            return f"{bytes_size:.2f} {unit}"
        bytes_size /= 1024
def scan_folder(path,allowed_ext):
    IGNORE_DIRS = {
    ".git",
    "__pycache__",
    "node_modules",
    ".cache",
    "venv",
    ".env"
    }
    if not os.path.isdir(path):
        raise HTTPException(status_code=400, detail="Invalid folder path")

    summary = defaultdict(lambda:{"count":0,"size":0})
    total_files=total_size=0
    for root, dirs, files in os.walk(path):
        dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]
        for file in files:
            full_path = os.path.join(root, file)

            if os.path.isfile(full_path):
                ext = os.path.splitext(file.lower())[1] or "others"
                if allowed_ext and ext not in allowed_ext:
                    continue
                size = os.path.getsize(full_path)

                summary[ext]["count"] += 1
                summary[ext]["size"] += size

                total_files += 1
                total_size += size
    return summary,total_files,total_size


@app.get("/",include_in_schema=False)
def home():
    return {"message": "Folder Analyzer API is running"}

@app.post("/analyze", tags=["Analyzer"])
async def analyze_folder(data: FolderRequest,
                   format: str = Query("json", enum=["json", "csv"]),
                   ext: str | None = Query(None, description="Comma separated extensions that you want to exclude")):
    path = data.path


    allowed_ext = set(e.strip().lower() for e in ext.split(",")) if ext else None
    summary,total_files,total_size=await asyncio.to_thread(scan_folder,path,allowed_ext)
    
    
    if format=='json':
        return {
        "path":path,
        "summary": {
            ext: { "count": summary[ext]["count"],
                    "size_bytes": summary[ext]["size"],
                    "size_human": human_size(summary[ext]["size"])}
                    for ext in sorted(summary)
        },
        "total_files": total_files,
        "total_size":total_size
    }

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["extension","count","sizebytes","Size"])
    for item in summary:
        writer.writerow([item,summary[item]["count"],summary[item]["size"],human_size(summary[item]["size"])])
    output.seek(0)
    return StreamingResponse(output,media_type="text/csv",headers={"Content-disposition":"attachment;filename=filesummary.csv"})

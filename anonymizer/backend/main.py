# Presidio Anonymizer
# Copyright (C) 2026 Sambruk
#
# Detta program är fri programvara; du får sprida och ändra det enligt
# villkoren i GNU General Public License version 2, som den publicerats av
# Free Software Foundation.
#
# Programmet distribueras i hopp om att det ska vara användbart, men UTAN
# NÅGON GARANTI. Se GNU General Public License för fler detaljer.
# Se filen LICENSE.

import os
import uuid
import asyncio
from typing import List, Optional
from fastapi import FastAPI, File, UploadFile, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
import aiofiles
from dotenv import load_dotenv
import logging

from document_processor import DocumentProcessor
from presidio_service import PresidioService

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Document Anonymizer API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_FOLDER = os.getenv("UPLOAD_FOLDER", "/tmp/uploads")
OUTPUT_FOLDER = os.getenv("OUTPUT_FOLDER", "/tmp/outputs")
MAX_FILE_SIZE = int(os.getenv("MAX_FILE_SIZE", 10485760))
ALLOWED_EXTENSIONS = os.getenv("ALLOWED_EXTENSIONS", "docx,xlsx,pdf,txt").split(",")

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

presidio_service = PresidioService()
document_processor = DocumentProcessor()

def allowed_file(filename: str) -> bool:
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.get("/")
async def root():
    return {"message": "Document Anonymizer API", "status": "running"}

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

@app.get("/api/health")
async def api_health_check():
    return {"status": "healthy"}

@app.post("/api/anonymize")
async def anonymize_document(file: UploadFile = File(...)):
    if not allowed_file(file.filename):
        raise HTTPException(
            status_code=400,
            detail=f"File type not allowed. Allowed types: {', '.join(ALLOWED_EXTENSIONS)}"
        )
    
    if file.size > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"File size exceeds maximum allowed size of {MAX_FILE_SIZE} bytes"
        )
    
    file_id = str(uuid.uuid4())
    file_extension = file.filename.rsplit('.', 1)[1].lower()
    input_path = os.path.join(UPLOAD_FOLDER, f"{file_id}.{file_extension}")
    output_path = os.path.join(OUTPUT_FOLDER, f"{file_id}_anonymized.{file_extension}")
    
    try:
        async with aiofiles.open(input_path, 'wb') as f:
            content = await file.read()
            await f.write(content)
        
        logger.info(f"Processing file: {file.filename}")
        
        text_content = await document_processor.extract_text(input_path, file_extension)
        
        analyzer_results = await presidio_service.analyze_text(text_content)
        
        anonymized_text = await presidio_service.anonymize_text(text_content, analyzer_results)
        
        await document_processor.create_anonymized_document(
            anonymized_text, 
            output_path, 
            file_extension,
            input_path
        )
        
        return FileResponse(
            output_path,
            media_type='application/octet-stream',
            filename=f"anonymized_{file.filename}"
        )
        
    except Exception as e:
        logger.error(f"Error processing file: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Processing error: {str(e)}")
    finally:
        if os.path.exists(input_path):
            os.remove(input_path)
        
        asyncio.create_task(cleanup_file(output_path, delay=300))

async def cleanup_file(filepath: str, delay: int):
    await asyncio.sleep(delay)
    try:
        if os.path.exists(filepath):
            os.remove(filepath)
            logger.info(f"Cleaned up file: {filepath}")
    except Exception as e:
        logger.error(f"Error cleaning up file {filepath}: {str(e)}")

@app.post("/api/analyze")
async def analyze_document(file: UploadFile = File(...)):
    if not allowed_file(file.filename):
        raise HTTPException(
            status_code=400,
            detail=f"File type not allowed. Allowed types: {', '.join(ALLOWED_EXTENSIONS)}"
        )
    
    file_id = str(uuid.uuid4())
    file_extension = file.filename.rsplit('.', 1)[1].lower()
    input_path = os.path.join(UPLOAD_FOLDER, f"{file_id}.{file_extension}")
    
    try:
        async with aiofiles.open(input_path, 'wb') as f:
            content = await file.read()
            await f.write(content)
        
        text_content = await document_processor.extract_text(input_path, file_extension)
        
        analyzer_results = await presidio_service.analyze_text(text_content)
        
        entities_found = {}
        for result in analyzer_results:
            entity_type = result.get("entity_type", "UNKNOWN")
            if entity_type not in entities_found:
                entities_found[entity_type] = []
            entities_found[entity_type].append({
                "text": text_content[result["start"]:result["end"]],
                "score": result.get("score", 0)
            })
        
        return JSONResponse(content={
            "filename": file.filename,
            "entities_found": entities_found,
            "total_entities": len(analyzer_results)
        })
        
    except Exception as e:
        logger.error(f"Error analyzing file: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if os.path.exists(input_path):
            os.remove(input_path)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
from fastapi import APIRouter, UploadFile, Body,File,FastAPI,Response,Depends, Form, Request,HTTPException,Query
from controller.DiskAnalyzer import DiskAnalyzer
from fastapi.responses import StreamingResponse 
from fastapi.responses import JSONResponse 
import json 
import asyncio 

from fastapi.responses import FileResponse   
 
 
 
 
router = APIRouter() 



@router.get("/listpart")
def listpart():
    analyser = DiskAnalyzer("C:\\", max_workers=5)
    result = analyser.display_disks_info()
    return result

@router.get("/analyseSubfile")
async def analyse_subfile(folder_name: str):
    analyser = DiskAnalyzer("C:\\", max_workers=5)
    queue = asyncio.Queue()

    async def producer():
        loop = asyncio.get_event_loop()
        
        def run():
            for item in analyser.analyze_subfolders(folder_name ):
                # ✅ Push chaque résultat dans la queue dès qu'il est prêt
                asyncio.run_coroutine_threadsafe(queue.put(item), loop)
            asyncio.run_coroutine_threadsafe(queue.put(None), loop)  # signal fin

        loop.run_in_executor(None, run)

    async def generator():
        asyncio.create_task(producer())
        while True:
            item = await queue.get()
            if item is None:  # fin du stream
                break
            yield f"data: {item}\n\n"

    return StreamingResponse(
        generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Access-Control-Allow-Origin": "*"
        }
    )

# # --- SIGNUP ---
# @router.post("/signup")
# def signup(username: str = Form(...), password: str = Form(...), immatricule: str = Form(...)):
#     return user.signup(username, password, immatricule)
# # --- SIGNUP ---



api_router = router
from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from src.routers import (
    user_router,
    auth_router,
    user_role_router,
    keyword_router,
    google_oauth_router,
    hubspot_router,
    serp_result_router,
    batch_history_router,
    contact_template_router,
    score_setting_router,
    dashboard_router,
    temp_test,
    sqs_monitor_router,
    client_router,
)
from src.config.logger import setup_logging
import os

setup_logging()   

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("FRONTEND_ORIGIN"),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"],
    max_age=600,
)

main_router = APIRouter(prefix="/api")

main_router.include_router(user_router)
main_router.include_router(auth_router)
main_router.include_router(user_role_router)
main_router.include_router(keyword_router)
main_router.include_router(google_oauth_router)
main_router.include_router(hubspot_router)
main_router.include_router(serp_result_router)
main_router.include_router(batch_history_router)
main_router.include_router(contact_template_router)
main_router.include_router(score_setting_router)
main_router.include_router(dashboard_router)
main_router.include_router(temp_test)
main_router.include_router(sqs_monitor_router)
main_router.include_router(client_router)

app.include_router(main_router)

@app.get("/")
async def read_root():
    return {"message": "hello world"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

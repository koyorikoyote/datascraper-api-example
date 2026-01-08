from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks, Query

from src.schemas import DashboardOut, TokenInfo, KeywordBulk, SerpResponse
from src.services import DashboardService
from src.services.temp_test_service import TempTestService
from src.services.selenium import SeleniumService
from src.utils.dependencies import get_service, get_current_user
from src.config.config import get_env

router = APIRouter(prefix="/temp-test", tags=["temp-test"])

TempTestServiceDep = Depends(get_service(TempTestService))

@router.post("/run-fetch-test/", response_model=list[SerpResponse])
def run_fetch_test(
    ids_in: KeywordBulk,
    service: TempTestService = TempTestServiceDep,
    token: TokenInfo = Depends(get_current_user),
):
    """
    Run fetch operation for testing without saving to database.
    This endpoint is similar to /keywords/run-fetch/ but doesn't save to the database.
    """
    return service.run_fetch_test(ids_in.ids, token)

@router.post("/run-rank-test/")
def run_rank_test(
    ids_in: KeywordBulk,
    service: TempTestService = TempTestServiceDep,
    token: TokenInfo = Depends(get_current_user),
):
    """
    Run rank operation for testing without saving to database.
    This endpoint is similar to /keywords/run-rank/ but doesn't save to the database.
    """
    return service.run_rank_test(ids_in.ids, token)

@router.post("/process-serp/{serp_id}/")
def process_single_serp(
    serp_id: int,
    service: TempTestService = TempTestServiceDep,
    token: TokenInfo = Depends(get_current_user),
):
    return service.process_single_serp(serp_id, token)

@router.get("/open-session/", response_model=None)
def open_session(
    background_tasks: BackgroundTasks,
    service: TempTestService = TempTestServiceDep,
    duration_seconds: int = Query(default=3600, description="How long to keep the session alive in seconds (default: 3600 = 1 hour)"),
    token: TokenInfo = Depends(get_current_user)
):
    """
    Open a Selenium session for testing VNC connection.
    Runs a background task that keeps the session alive for the specified duration.
    
    Args:
        duration_seconds: How long to keep the session alive in seconds (default: 3600 = 1 hour)
    """
    try:
        # Start Selenium session
        selenium_service = SeleniumService(headless=False)
        session_id = selenium_service.init_session()
        
        # Store the service instance to keep it alive
        service.active_sessions[session_id] = selenium_service
        
        # Start background task to keep session alive for specified duration
        background_tasks.add_task(
            service.keep_session_alive,
            session_id,
            selenium_service,
            duration_seconds
        )
        
        # Return session id and VNC link immediately
        return {
            "status": "processing",
            "session_id": session_id,
            "link": f"{get_env('SELENIUM_UI_URL', required=True)}#/session/{session_id}",
            "duration_seconds": duration_seconds,
            "message": f"Session opened and will stay alive for {duration_seconds} seconds. Use /invalidate-session/{session_id} to close it earlier."
        }
        
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )

@router.delete("/invalidate-session/{session_id}/", response_model=None)
def invalidate_session(
    session_id: str,
    service: TempTestService = TempTestServiceDep,
    token: TokenInfo = Depends(get_current_user)
):
    """
    Invalidate/close a Selenium session.
    """
    try:
        if session_id not in service.active_sessions:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Session {session_id} not found or already closed"
            )
        
        # Get the selenium service and clean it up
        selenium_service = service.active_sessions[session_id]
        selenium_service._cleanup(force=True)
        
        # Remove from active sessions
        del service.active_sessions[session_id]
        
        return {
            "status": "session_closed",
            "session_id": session_id,
            "message": "Session invalidated successfully"
        }
        
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )

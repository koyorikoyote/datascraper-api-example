from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.orm import Session
import boto3
from botocore.exceptions import ClientError
import logging

from src.utils.dependencies import get_service, get_current_user, get_db
from src.services import HubspotService
from src.schemas import TokenInfo, BatchHistoryDetailCreate, BatchHistoryUpdate
from src.utils.constants import StatusConst
from src.models.serp_result import SerpResult
from src.models.user_role import UserRole
from src.config.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/client", tags=["client"])

HubspotDep = Depends(get_service(HubspotService))

class ProgressPayload(BaseModel):
    company_id: str
    domain: str
    status: str
    error_message: Optional[str] = None
    batch_id: Optional[int] = None

class ContactResultPayload(BaseModel):
    id: int
    contact_send_success: bool

class SaveResultsPayload(BaseModel):
    results: list[ContactResultPayload]

@router.post("/progress")
def report_progress(
    payload: ProgressPayload,
    service: HubspotService = HubspotDep,
    token: TokenInfo = Depends(get_current_user)
):
    try:
        # Update BatchHistoryDetail
        if payload.batch_id:
            service.batch_history_detail_repo.create(
                BatchHistoryDetailCreate(
                    batch_id=payload.batch_id,
                    target=payload.domain,
                    status=payload.status,
                    error_message=payload.error_message,
                )
            )
            
            # Update company status
            company_update = [{
                "id": payload.company_id,
                "properties": {
                    "status": StatusConst.SUCCESS if payload.status == "success" else StatusConst.FAILED,
                    "batch_id": payload.batch_id
                }
            }]
            
            service._batch_update_companies(token, company_update)
            
        return {"status": "ok"}
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

@router.post("/save-results")
def save_results(
    payload: SaveResultsPayload,
    db: Session = Depends(get_db),
    token: TokenInfo = Depends(get_current_user)
):
    try:
        for result in payload.results:
            serp_result = db.query(SerpResult).filter(SerpResult.id == result.id).first()
            if serp_result:
                serp_result.contact_send_success = result.contact_send_success
        
        db.commit()
        return {"status": "ok", "updated_count": len(payload.results)}
    except Exception as exc:
        db.rollback()
        logger.error(f"Error saving results: {exc}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

@router.get("/domains")
def get_domains(
    limit: int = 10,
    db: Session = Depends(get_db),
    token: TokenInfo = Depends(get_current_user)
):
    # Fetch last N records from serp_result
    # All users can access this endpoint - role_id only determines frontend behavior
    
    results = db.query(SerpResult).order_by(SerpResult.id.desc()).limit(limit).all()
    
    # Check if user is 'system' role
    user_role = db.query(UserRole).filter(UserRole.id == token.role_id).first()
    is_system = user_role and user_role.role_name == 'system'
    
    domains = []
    for r in results:
        if is_system:
            # For system users: use url_corporate_site if available, else link
            # Only include if at least one of them exists
            url = r.url_corporate_site if r.url_corporate_site else r.link
            if url:
                domains.append({"id": r.id, "domain": url, "title": r.title or ""})
        else:
            # For other users: use domain_name
            if r.domain_name:
                domains.append({"id": r.id, "domain": r.domain_name, "title": r.title or ""})
    
    return domains

@router.get("/download-url")
def get_download_url(
    token: TokenInfo = Depends(get_current_user)
):
    """
    Generate a presigned URL for downloading the local client executable.
    The URL is valid for 5 minutes and requires authentication.
    """
    try:
        # Get AWS credentials from settings
        aws_region = settings.get("AWS_REGION") or "ap-northeast-1"
        aws_access_key = settings.get("AWS_ACCESS_KEY_ID")
        aws_secret_key = settings.get("AWS_SECRET_ACCESS_KEY")
        
        # Initialize S3 client
        if aws_access_key and aws_secret_key:
            s3_client = boto3.client(
                's3',
                region_name=aws_region,
                aws_access_key_id=aws_access_key,
                aws_secret_access_key=aws_secret_key
            )
        else:
            s3_client = boto3.client('s3', region_name=aws_region)
        
        # Generate presigned URL
        bucket_name = "sales-assistant-web-prod"
        object_key = "local/SalesAssistantClient.exe"
        expiration = 300  # 5 minutes
        
        presigned_url = s3_client.generate_presigned_url(
            'get_object',
            Params={
                'Bucket': bucket_name,
                'Key': object_key
            },
            ExpiresIn=expiration
        )
        
        logger.info(f"Generated presigned URL for user {token.id}")
        
        return {
            "download_url": presigned_url,
            "expires_in": expiration
        }
        
    except ClientError as e:
        logger.error(f"AWS S3 error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate download URL"
        )
    except Exception as e:
        logger.error(f"Error generating presigned URL: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate download URL"
        )


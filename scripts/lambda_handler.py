import json, urllib.request, urllib.error, urllib.parse

# API endpoints
AUTH_ENDPOINT = "http://sales-assistant-alb-1943524217.ap-northeast-1.elb.amazonaws.com/api/auth/login/"
ENDPOINT = "http://sales-assistant-alb-1943524217.ap-northeast-1.elb.amazonaws.com/api/keywords/run-fetch-and-rank-scheduled/"

def lambda_handler(event, context):
    try:
        # Step 1: Get authentication token
        auth_data = urllib.parse.urlencode({
            "username": "takeushi001@gmail.com",  # User ID 2
            "password": "admin"
        }).encode()
        
        auth_req = urllib.request.Request(
            AUTH_ENDPOINT, 
            data=auth_data,
            method="POST",
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )
        
        with urllib.request.urlopen(auth_req, timeout=30) as auth_resp:
            auth_result = json.loads(auth_resp.read().decode())
            access_token = auth_result.get("access_token")
            
            if not access_token:
                return {
                    "statusCode": 401,
                    "body": "Failed to obtain authentication token"
                }
        
        # Step 2: Call the endpoint with authentication
        # This is an extremely long-running API call (up to 2 hours)
        # We need to fire and forget - just initiate the request without waiting for completion
        req = urllib.request.Request(
            ENDPOINT,
            method="POST",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {access_token}"
            }
        )
        
        # Set a short timeout just to ensure the request is accepted
        # We don't need or want the actual response data
        conn = urllib.request.urlopen(req, timeout=30)
        
        # Just check the status code to confirm the request was accepted
        status = conn.status
        
        # Close the connection immediately without reading the response
        # This allows the server to continue processing asynchronously
        conn.close()
        
        if status in (200, 201, 202, 204):
            return {
                "statusCode": status,
                "body": json.dumps({
                    "message": "Request successfully initiated. The API will continue processing for approximately 2 hours.",
                    "status": "accepted"
                })
            }
        else:
            return {
                "statusCode": status,
                "body": json.dumps({
                    "message": f"Request failed with status: {status}",
                    "status": "failed"
                })
            }
            
    except urllib.error.HTTPError as e:
        return {"statusCode": e.code, "body": e.read().decode()}
    except Exception as e:
        return {"statusCode": 500, "body": str(e)}

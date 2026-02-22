from fastapi import FastAPI, Request, Depends, HTTPException, Form, BackgroundTasks
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import requests
import datetime
from sqlalchemy.orm import Session
import database as db
import config
from typing import Optional

app = FastAPI()
db.init_db()

# Static and Templates
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

def get_db():
    session = db.SessionLocal()
    try:
        yield session
    finally:
        session.close()

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    # VaultCord style verification landing page
    return templates.TemplateResponse("index.html", {"request": request, "client_id": config.CLIENT_ID, "redirect_uri": config.REDIRECT_URI})

@app.get("/login")
async def login():
    # Redirect to Discord OAuth2
    url = f"https://discord.com/api/oauth2/authorize?client_id={config.CLIENT_ID}&redirect_uri={config.REDIRECT_URI}&response_type=code&scope=identify+guilds.join"
    return RedirectResponse(url)

@app.get("/callback")
async def callback(code: str, request: Request, dbs: Session = Depends(get_db)):
    # Exchange code for token
    data = {
        'client_id': config.CLIENT_ID,
        'client_secret': config.CLIENT_SECRET,
        'grant_type': 'authorization_code',
        'code': code,
        'redirect_uri': config.REDIRECT_URI
    }
    headers = {'Content-Type': 'application/x-www-form-urlencoded'}
    r = requests.post("https://discord.com/api/oauth2/token", data=data, headers=headers)
    
    if r.status_code != 200:
        return HTMLResponse("Failed to verify. Please try again.", status_code=400)
    
    token_data = r.json()
    access_token = token_data['access_token']
    refresh_token = token_data['refresh_token']
    expires_in = token_data['expires_in']
    
    # Get User Info
    user_r = requests.get("https://discord.com/api/users/@me", headers={'Authorization': f"Bearer {access_token}"})
    user_info = user_r.json()
    
    # Save/Update in DB
    existing_member = dbs.query(db.Member).filter(db.Member.user_id == user_info['id']).first()
    expiry_date = datetime.datetime.utcnow() + datetime.timedelta(seconds=expires_in)
    
    if existing_member:
        existing_member.access_token = access_token
        existing_member.refresh_token = refresh_token
        existing_member.expires_at = expiry_date
        existing_member.username = user_info['username']
        existing_member.ip_address = request.client.host
    else:
        new_member = db.Member(
            user_id=user_info['id'],
            username=user_info['username'],
            avatar=user_info['avatar'],
            access_token=access_token,
            refresh_token=refresh_token,
            expires_at=expiry_date,
            ip_address=request.client.host
        )
        dbs.add(new_member)
    
    dbs.commit()
    
    return templates.TemplateResponse("success.html", {"request": request, "user": user_info})

from typing import Optional

@app.get("/admin", response_class=HTMLResponse)
async def admin_panel(request: Request, password: Optional[str] = None, dbs: Session = Depends(get_db)):
    if password != config.ADMIN_PASSWORD:
        return HTMLResponse("Unauthorized", status_code=401)
    
    members = dbs.query(db.Member).all()
    return templates.TemplateResponse("dashboard.html", {"request": request, "members": members, "count": len(members), "password": password})

async def refresh_user_tokens(dbs: Session):
    """
    Background worker to keep the Vault tokens valid.
    """
    now = datetime.datetime.utcnow()
    # Find tokens expiring in the next 7 days (broad window for safety)
    expiring_soon = dbs.query(db.Member).filter(db.Member.expires_at < now + datetime.timedelta(days=7)).all()
    
    refreshed = 0
    failed = 0
    
    for member in expiring_soon:
        data = {
            'client_id': config.CLIENT_ID,
            'client_secret': config.CLIENT_SECRET,
            'grant_type': 'refresh_token',
            'refresh_token': member.refresh_token
        }
        headers = {'Content-Type': 'application/x-www-form-urlencoded'}
        try:
            r = requests.post("https://discord.com/api/oauth2/token", data=data, headers=headers, timeout=5)
            if r.status_code == 200:
                new_data = r.json()
                member.access_token = new_data['access_token']
                member.refresh_token = new_data['refresh_token']
                member.expires_at = now + datetime.timedelta(seconds=new_data['expires_in'])
                member.last_updated = now
                refreshed += 1
            else:
                failed += 1
        except Exception:
            failed += 1
    
    dbs.commit()
    return refreshed, failed

@app.post("/admin/sync")
async def sync_tokens(background_tasks: BackgroundTasks, password: str = Form(...), dbs: Session = Depends(get_db)):
    if password != config.ADMIN_PASSWORD:
        return {"error": "Unauthorized"}
    
    background_tasks.add_task(refresh_user_tokens, dbs)
    return {"status": "sync_initiated"}

@app.post("/admin/restore")
async def restore_members(guild_id: str = Form(...), password: str = Form(...), dbs: Session = Depends(get_db)):
    if password != config.ADMIN_PASSWORD:
        return {"error": "Unauthorized"}

    members = dbs.query(db.Member).all()
    restored_count = 0
    failed_count = 0
    
    for member in members:
        # Add to guild: PUT /guilds/{guild_id}/members/{user_id}
        url = f"https://discord.com/api/guilds/{guild_id}/members/{member.user_id}"
        headers = {
            "Authorization": f"Bot {config.BOT_TOKEN}",
            "Content-Type": "application/json"
        }
        body = {
            "access_token": member.access_token
        }
        
        try:
            r = requests.put(url, json=body, headers=headers, timeout=5)
            if r.status_code in [201, 204]:
                restored_count += 1
            else:
                failed_count += 1
        except Exception:
            failed_count += 1
            
    return {"status": "success", "restored": restored_count, "failed": failed_count}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

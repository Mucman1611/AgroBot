from fastapi import FastAPI, Depends, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from typing import Optional
import models, schemas, auth
from database import get_db, engine
import json

models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="AgriAssistant API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_current_user(authorization: Optional[str] = Header(None), db: Session = Depends(get_db)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Nije autoriziran")
    token = authorization.split(" ")[1]
    user_id = auth.verify_token(token)
    if not user_id:
        raise HTTPException(status_code=401, detail="Nevažeći token")
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=401, detail="Korisnik ne postoji")
    return user

@app.post("/api/register")
def register(data: schemas.RegisterRequest, db: Session = Depends(get_db)):
    existing = db.query(models.User).filter(models.User.email == data.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email već postoji")
    user = models.User(
        full_name=data.full_name,
        email=data.email,
        password_hash=auth.hash_password(data.password),
        role=data.role,
        delegated_to_id=data.delegated_to_id
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return {"message": "Registracija uspješna", "id": user.id}

@app.post("/api/login")
def login(data: schemas.LoginRequest, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == data.email).first()
    if not user or not auth.verify_password(data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Pogrešan email ili lozinka")
    token = auth.create_token(user.id)
    return {"token": token, "role": user.role, "user_id": user.id, "full_name": user.full_name}

@app.get("/api/user/by-email")
def get_user_by_email(email: str, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == email).first()
    if not user:
        raise HTTPException(status_code=404, detail="Korisnik nije pronađen")
    return {"id": user.id, "full_name": user.full_name}

@app.get("/api/farmer/farms")
def get_farmer_farms(current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    farms = db.query(models.Farm).filter(models.Farm.owner_id == current_user.id).all()
    result = []
    for farm in farms:
        deadlines = db.query(models.Deadline).filter(models.Deadline.farm_id == farm.id).all()
        result.append({
            "id": farm.id,
            "name": farm.name,
            "location": farm.location,
            "total_area_ha": farm.total_area_ha,
            "deadlines": [{"id": d.id, "competition_name": d.competition_name, "deadline_date": str(d.deadline_date), "status": d.status} for d in deadlines]
        })
    return result

@app.post("/api/farmer/farms/add")
def add_farmer_farm(data: schemas.FarmCreate, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    farm = models.Farm(
        name=data.name,
        location=data.location,
        total_area_ha=data.total_area_ha,
        owner_id=current_user.id,
        agent_id=None
    )
    db.add(farm)
    db.commit()
    db.refresh(farm)
    return {"id": farm.id, "message": "OPG dodan"}

@app.get("/api/agent/farms")
def get_agent_farms(current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    if current_user.role != "agent":
        raise HTTPException(status_code=403, detail="Samo agenti imaju pristup")
    farms = db.query(models.Farm).filter(models.Farm.agent_id == current_user.id).all()
    result = []
    for farm in farms:
        deadlines = db.query(models.Deadline).filter(models.Deadline.farm_id == farm.id).all()
        applications = db.query(models.Application).filter(models.Application.farm_id == farm.id).all()
        result.append({
            "id": farm.id,
            "name": farm.name,
            "location": farm.location,
            "total_area_ha": farm.total_area_ha,
            "parcels_count": farm.parcels_count,
            "deadlines": [{"id": d.id, "competition_name": d.competition_name, "deadline_date": str(d.deadline_date), "status": d.status} for d in deadlines],
            "applications": [{"id": a.id, "competition_name": a.competition_name, "submitted_date": str(a.submitted_date), "status": a.status, "signed": a.signed} for a in applications]
        })
    return result

@app.post("/api/agent/farms/add")
def add_agent_farm(data: schemas.AgentFarmCreate, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    if current_user.role != "agent":
        raise HTTPException(status_code=403, detail="Samo agenti imaju pristup")
    owner = db.query(models.User).filter(models.User.email == data.owner_email).first()
    if not owner:
        new_owner = models.User(
            full_name=data.owner_email.split("@")[0],
            email=data.owner_email,
            password_hash=auth.hash_password("temp1234"),
            role="farmer"
        )
        db.add(new_owner)
        db.commit()
        db.refresh(new_owner)
        owner = new_owner
    farm = models.Farm(
        name=data.name,
        location=data.location,
        total_area_ha=data.total_area_ha,
        owner_id=owner.id,
        agent_id=current_user.id
    )
    db.add(farm)
    db.commit()
    db.refresh(farm)
    deadline = models.Deadline(
        farm_id=farm.id,
        competition_name="IAKS 2025 - Izravna plaćanja",
        deadline_date=datetime.now() + timedelta(days=14),
        status="pending"
    )
    db.add(deadline)
    db.commit()
    return {"id": farm.id, "message": "OPG dodan"}

@app.post("/api/agent/farm/{farm_id}/submit")
def submit_application(farm_id: int, data: schemas.ApplicationSubmit, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    if current_user.role != "agent":
        raise HTTPException(status_code=403, detail="Samo agenti imaju pristup")
    farm = db.query(models.Farm).filter(models.Farm.id == farm_id, models.Farm.agent_id == current_user.id).first()
    if not farm:
        raise HTTPException(status_code=404, detail="OPG nije pronađen")
    competition = db.query(models.Competition).filter(models.Competition.id == data.competition_id).first()
    if not competition:
        raise HTTPException(status_code=404, detail="Natječaj nije pronađen")
    application = models.Application(
        farm_id=farm_id,
        competition_name=competition.name,
        submitted_date=datetime.now(),
        status="pending",
        signed=False,
        notes=data.notes
    )
    db.add(application)
    db.commit()
    return {"message": "Prijava poslana klijentu na potpis"}

@app.get("/api/agent/calendar")
def get_calendar(month: int = 0, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    if current_user.role != "agent":
        raise HTTPException(status_code=403, detail="Samo agenti imaju pristup")
    farms = db.query(models.Farm).filter(models.Farm.agent_id == current_user.id).all()
    farm_ids = [f.id for f in farms]
    farm_map = {f.id: f.name for f in farms}
    if not farm_ids:
        return []
    year = datetime.now().year
    deadlines = db.query(models.Deadline).filter(
        models.Deadline.farm_id.in_(farm_ids)
    ).all()
    result = []
    for d in deadlines:
        dl_date = d.deadline_date if isinstance(d.deadline_date, datetime) else datetime.combine(d.deadline_date, datetime.min.time())
        if dl_date.month == month + 1:
            days_until = (dl_date - datetime.now()).days
            result.append({
                "date": dl_date.strftime("%Y-%m-%d"),
                "farm_name": farm_map.get(d.farm_id, ""),
                "competition_name": d.competition_name,
                "days_until": days_until
            })
    return result

@app.get("/api/competitions/available")
def get_competitions(current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    competitions = db.query(models.Competition).filter(models.Competition.active == True).all()
    return [{"id": c.id, "name": c.name, "deadline": str(c.deadline)} for c in competitions]

@app.post("/api/voice/command")
async def voice_command(current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    farms = db.query(models.Farm).filter(models.Farm.owner_id == current_user.id).all()
    count = len(farms)
    return {"status": "success", "message": f"✅ Glasovna naredba primljena! Pronađeno {count} parcela za prijavu.", "action": "submit_all"}

@app.post("/api/seed")
def seed_data(db: Session = Depends(get_db)):
    if db.query(models.Competition).count() > 0:
        return {"message": "Podaci već postoje"}
    competitions = [
        models.Competition(name="IAKS 2025 - Izravna plaćanja", deadline=datetime.now() + timedelta(days=30), active=True),
        models.Competition(name="Ruralni razvoj - mjera 4.1", deadline=datetime.now() + timedelta(days=45), active=True),
        models.Competition(name="LEADER program 2025", deadline=datetime.now() + timedelta(days=60), active=True),
        models.Competition(name="Ekološka poljoprivreda - potpora", deadline=datetime.now() + timedelta(days=20), active=True),
    ]
    for c in competitions:
        db.add(c)
    agent = models.User(full_name="Zdenka Pavlović", email="zdenka@agri.hr", password_hash=auth.hash_password("agent123"), role="agent")
    farmer = models.User(full_name="Franjo Horvat", email="franjo@opg.hr", password_hash=auth.hash_password("farmer123"), role="farmer")
    db.add(agent)
    db.add(farmer)
    db.commit()
    db.refresh(agent)
    db.refresh(farmer)
    farm1 = models.Farm(name="OPG Horvat", location="Varaždin", total_area_ha=12.5, parcels_count=4, owner_id=farmer.id, agent_id=agent.id)
    farm2 = models.Farm(name="OPG Kovačević", location="Koprivnica", total_area_ha=8.3, parcels_count=3, owner_id=farmer.id, agent_id=agent.id)
    farm3 = models.Farm(name="OPG Babić", location="Osijek", total_area_ha=22.0, parcels_count=6, owner_id=farmer.id, agent_id=agent.id)
    db.add(farm1)
    db.add(farm2)
    db.add(farm3)
    db.commit()
    db.refresh(farm1)
    db.refresh(farm2)
    db.refresh(farm3)
    deadlines = [
        models.Deadline(farm_id=farm1.id, competition_name="IAKS 2025 - Izravna plaćanja", deadline_date=datetime.now() + timedelta(days=5), status="pending"),
        models.Deadline(farm_id=farm1.id, competition_name="Ruralni razvoj - mjera 4.1", deadline_date=datetime.now() + timedelta(days=14), status="pending"),
        models.Deadline(farm_id=farm2.id, competition_name="LEADER program 2025", deadline_date=datetime.now() + timedelta(days=3), status="pending"),
        models.Deadline(farm_id=farm3.id, competition_name="Ekološka poljoprivreda - potpora", deadline_date=datetime.now() + timedelta(days=7), status="pending"),
    ]
    for d in deadlines:
        db.add(d)
    applications = [
        models.Application(farm_id=farm1.id, competition_name="IAKS 2024", submitted_date=datetime.now() - timedelta(days=30), status="approved", signed=True),
        models.Application(farm_id=farm2.id, competition_name="Ruralni razvoj 2024", submitted_date=datetime.now() - timedelta(days=10), status="pending", signed=False),
    ]
    for a in applications:
        db.add(a)
    db.commit()
    return {"message": "Test podaci dodani. Agent: zdenka@agri.hr / agent123, Farmer: franjo@opg.hr / farmer123"}
import os
import json
import uuid
from fastapi import FastAPI, Form, File, UploadFile, HTTPException
from pydantic import BaseModel
from firebase_admin import credentials, initialize_app, firestore, auth

# Load Firebase credentials from the environment variable (expects a file path)
firebase_credentials_path = os.getenv("FIREBASE_CREDENTIALS")

if not firebase_credentials_path or not os.path.exists(firebase_credentials_path):
    raise RuntimeError(f"Firebase credentials file not found at: {firebase_credentials_path}")

try:
    with open(firebase_credentials_path, "r") as file:
        cred_dict = json.load(file)  # Load JSON content from file
    cred = credentials.Certificate(cred_dict)  # Initialize Firebase
    initialize_app(cred)
    db = firestore.client()  # Initialize Firestore
except json.JSONDecodeError:
    raise RuntimeError("FIREBASE_CREDENTIALS file is not valid JSON. Please check the content.")

app = FastAPI()

# User Registration
@app.post("/register/")
async def register_user(
    name: str = Form(...),
    email: str = Form(...),
    phone: str = Form(...),
    id_proof: UploadFile = File(...)
):
    user_id = str(uuid.uuid4())
    id_proof_filename = f"{user_id}_{id_proof.filename}"

    try:
        user = auth.create_user(email=email, phone_number=f"+{phone}")
        user_id = user.uid
    except auth.EmailAlreadyExistsError:
        raise HTTPException(status_code=400, detail="Email already registered")

    user_data = {"name": name, "email": email, "phone": phone, "id_proof": id_proof_filename, "verified": False}
    db.collection("users").document(user_id).set(user_data)

    return {"message": "User registered successfully", "user_id": user_id}

# User Login
class LoginRequest(BaseModel):
    email: str
    phone: str

@app.post("/login")
def login_user(login_data: LoginRequest):
    try:
        user = auth.get_user_by_email(login_data.email)
        if user.phone_number != login_data.phone:
            raise HTTPException(status_code=401, detail="Invalid credentials")
        return {"message": "Login successful", "user_id": user.uid}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# Help Request System
class HelpRequest(BaseModel):
    user_id: str
    category: str
    description: str
    location: str

@app.post("/request_help/")
def request_help(request: HelpRequest):
    request_id = str(uuid.uuid4())
    request_data = request.dict()
    request_data["status"] = "open"
    db.collection("help_requests").document(request_id).set(request_data)
    return {"message": "Help request created successfully", "request_id": request_id}

# Volunteer System
@app.get("/view_requests/")
def view_requests():
    requests = db.collection("help_requests").where("status", "==", "open").stream()
    return [{"request_id": req.id, **req.to_dict()} for req in requests]

class VolunteerAccept(BaseModel):
    request_id: str
    volunteer_id: str

@app.post("/accept_request/")
def accept_request(data: VolunteerAccept):
    request_ref = db.collection("help_requests").document(data.request_id)
    request_doc = request_ref.get()
    if not request_doc.exists:
        raise HTTPException(status_code=404, detail="Request not found")
    request_ref.update({"status": "accepted", "volunteer_id": data.volunteer_id})
    return {"message": "Request accepted successfully"}

# Placeholder for Chat System
@app.post("/chat/")
def chat_system():
    return {"message": "Chat system coming soon!"}

# Debug Endpoint to Check Environment Variables
@app.get("/debug/env")
def debug_env():
    return {"FIREBASE_CREDENTIALS": firebase_credentials_path}

import os

PORT = os.getenv("PORT", 8000)  # Default to 8000 if not set
DATABASE_URL = os.getenv("DATABASE_URL")
SECRET_KEY = os.getenv("SECRET_KEY")

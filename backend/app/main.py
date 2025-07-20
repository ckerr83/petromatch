from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .routers import auth, user, jobs, notifications
from .core.database import engine, Base

# Create database tables
Base.metadata.create_all(bind=engine)

app = FastAPI(title="PetroMatch API", version="1.0.0")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000", 
        "https://petromatch-app.vercel.app",
        "https://*.vercel.app"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router)
app.include_router(user.router)
app.include_router(jobs.router)
app.include_router(notifications.router)

@app.get("/")
def read_root():
    return {"message": "PetroMatch API"}
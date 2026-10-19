from fastapi import FastAPI
from app.routers import billing

app = FastAPI()
app.include_router(billing.router)

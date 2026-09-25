from fastapi import FastAPI
from app.api.repository_api import router as repository_router
app = FastAPI()

@app.get("/health")
def health_check():
    return {"status": "healthy"}

app.include_router(repository_router)

    
from fastapi import FastAPI   
from api.api import api_router   
from fastapi.middleware.cors import CORSMiddleware

import socket

app = FastAPI()


# Middleware CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",   # si tu y accèdes depuis un autre PC
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

print(f"🚀 Serveur démarré sur {socket.gethostname()} (IP: {socket.gethostbyname(socket.gethostname())})")

# Enregistrer les routes de l'API
app.include_router(api_router, prefix="/api") 

# Pour lancer : uvicorn app:app --reload --port 8081

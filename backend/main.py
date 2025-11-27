from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.chatbotapi import router as chatbot_router
from backend.loginauth import router as auth_router
from backend.signupauth import router as signup_router
from backend.analyzetweets import router as analyze_router
from backend.googlefit import router as googlefit_router
from backend.habit import router as habit_router
from backend.journal import router as journal_router

app = FastAPI()


app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # 👈 match your frontend port!
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chatbot_router)
app.include_router(auth_router)
app.include_router(signup_router)
app.include_router(analyze_router)
app.include_router(googlefit_router)
app.include_router(habit_router)
app.include_router(journal_router)
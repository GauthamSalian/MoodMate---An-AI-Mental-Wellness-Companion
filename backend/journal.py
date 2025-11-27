from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List
from uuid import uuid4
from datetime import date, datetime
from sqlalchemy.orm import Session
from .database import Base, SessionLocal, engine
from . import models
import requests
import os
from dotenv import load_dotenv
import boto3
from decimal import Decimal
load_dotenv()
from ibm_watsonx_ai.foundation_models import ModelInference
from ibm_watsonx_ai.credentials import Credentials
from ibm_watsonx_ai import APIClient
import re

# Watsonx credentials
credentials = Credentials(
    url="https://eu-de.ml.cloud.ibm.com",
    api_key=os.getenv("WATSONX_API_KEY")
)
client = APIClient(credentials)

guardian_model = ModelInference(
    model_id="ibm/granite-3-3-8b-instruct",
    credentials=credentials,
    project_id="1cb8c38f-d650-41fe-9836-86659006c090",
    params={"decoding_method": "greedy", "max_new_tokens": 100}
)


AWS_REGION = "ap-south-1"
DYNAMO_TABLE = "UserMemory"
FIXED_USER_ID = "demo_user"

dynamodb = boto3.resource("dynamodb", region_name=AWS_REGION)
dynamo_table = dynamodb.Table(DYNAMO_TABLE)

def get_granite_stress_score(text: str):
    prompt = f"""
    <risk_evaluation>
    <text>{text}</text>

    Analyze this text for emotional or psychological risk. Respond using structured XML format:

    <harm>[Yes or No]</harm>
    <confidence>[Numeric probability between 0.0 (no risk) and 1.0 (high risk)]</confidence>
    <comment>[Brief reason why the risk was assessed]</comment>
    </risk_evaluation>
    """
    try:
        response = guardian_model.generate(prompt)
        result = response["results"][0]["generated_text"]

        harm = re.search(r"<harm>(.*?)</harm>", result)
        confidence = re.search(r"<confidence>(.*?)</confidence>", result)
        comment = re.search(r"<comment>(.*?)</comment>", result)

        harm_val = harm.group(1).strip() if harm else "Unknown"
        score_val = float(confidence.group(1).strip()) if confidence else 0.0
        comment_val = comment.group(1).strip() if comment else "Not provided"

        return {
            "risk_detected": harm_val,
            "stress_score": round(score_val, 3),
            "risk_comment": comment_val
        }
    except Exception as e:
        print("⚠️ Granite risk check failed:", e)
        return {
            "risk_detected": "Unknown",
            "stress_score": 0.0,
            "risk_comment": "Error during analysis"
        }


def convert_floats_to_decimal(obj):
    if isinstance(obj, float):
        return Decimal(str(obj))
    elif isinstance(obj, list):
        return [convert_floats_to_decimal(i) for i in obj]
    elif isinstance(obj, dict):
        return {k: convert_floats_to_decimal(v) for k, v in obj.items()}
    else:
        return obj

def save_to_dynamodb(item: dict):
    item["user_id"] = FIXED_USER_ID
    item = convert_floats_to_decimal(item)
    try:
        dynamo_table.put_item(Item=item)
    except Exception as e:
        print(f"❌ DynamoDB Upload Error (id={item.get('id')}):", e)


HF_API_TOKEN = os.getenv("HF_API_TOKEN")
if HF_API_TOKEN is None:
    raise RuntimeError("HF_API_TOKEN not found. Check your .env file.")

HUGGINGFACE_API_URL = "https://api-inference.huggingface.co/models/j-hartmann/emotion-english-distilroberta-base"
HEADERS = {
    "Authorization": f"Bearer {HF_API_TOKEN}",
}

# Initialize DB and app
models.Base.metadata.create_all(bind=engine)
router = APIRouter()

# Pydantic models
class AllEmotionScore(BaseModel):
    emotion: str
    score: float

class WordEmotionOut(BaseModel):
    text: str
    emotion: str
    score: float

    class Config:
        orm_mode = True

class JournalEntryResponse(BaseModel):
    id: str
    text: str
    date: date
    dominant_emotion: str
    dominant_score: float
    all_emotions: List[AllEmotionScore]
    word_emotions: List[WordEmotionOut]

    class Config:
        orm_mode = True

class JournalRequest(BaseModel):
    text: str
    date: date

class JournalEditRequest(BaseModel):
    text: str

# Database dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Emotion analysis via Hugging Face API
def call_emotion_api(text: str):
    try:
        response = requests.post(
            HUGGINGFACE_API_URL,
            headers=HEADERS,
            json={"inputs": text}
        )
        response.raise_for_status()
        return response.json()[0]
    except requests.exceptions.RequestException as e:
        raise HTTPException(status_code=500, detail=f"Emotion API call failed: {str(e)}")

def analyze_emotions(text: str):
    full_text_results = call_emotion_api(text)
    dominant_emotion = full_text_results[0]['label'].lower()
    dominant_score = round(full_text_results[0]['score'], 3)
    all_emotions = [
        {"emotion": res['label'].lower(), "score": round(res['score'], 3)}
        for res in full_text_results
    ]

    words = text.split()
    word_emotions = []
    for word in words:
        word_result = call_emotion_api(word)
        result = word_result[0]
        word_emotions.append({
            "text": word,
            "emotion": result['label'].lower(),
            "score": round(result['score'], 3)
        })

    return dominant_emotion, dominant_score, all_emotions, word_emotions

# Routes
@router.post("/journal-entry", response_model=JournalEntryResponse)
def create_journal_entry(entry: JournalRequest, db: Session = Depends(get_db)):
    existing = db.query(models.JournalEntry).filter(models.JournalEntry.date == entry.date).first()
    if existing:
        raise HTTPException(status_code=400, detail="Journal entry for this date already exists")

    # Emotion analysis
    dominant_emotion, dominant_score, all_emotions, word_emotions_data = analyze_emotions(entry.text)

    # Granite risk score
    granite_result = get_granite_stress_score(entry.text)
    stress_score = granite_result["stress_score"]
    risk_detected = granite_result["risk_detected"]
    risk_comment = granite_result["risk_comment"]

    # Create journal entry
    journal_id = str(uuid4())
    journal = models.JournalEntry(
        id=journal_id,
        text=entry.text,
        date=entry.date,
        dominant_emotion=dominant_emotion,
        dominant_score=dominant_score,
        all_emotions=all_emotions
    )
    for word in word_emotions_data:
        journal.word_emotions.append(models.WordEmotion(
            id=str(uuid4()),
            text=word['text'],
            emotion=word['emotion'],
            score=word['score']
        ))

    db.add(journal)
    db.commit()
    db.refresh(journal)

    # Save full data to DynamoDB
    save_to_dynamodb({
        "id": journal.id,
        "text": journal.text,
        "date": journal.date.isoformat(),
        "dominant_emotion": dominant_emotion,
        "dominant_score": dominant_score,
        "stress_score": stress_score,
        "risk_detected": risk_detected,
        "risk_comment": risk_comment,
        "all_emotions": all_emotions,
        "word_emotions": word_emotions_data
    })

    return {
        "id": journal.id,
        "text": journal.text,
        "date": journal.date,
        "dominant_emotion": dominant_emotion,
        "dominant_score": dominant_score,
        "stress_score": stress_score,
        "all_emotions": all_emotions,
        "word_emotions": word_emotions_data
    }


@router.put("/journal-entry/{entry_id}", response_model=JournalEntryResponse)
def update_journal_entry(entry_id: str, request: JournalEditRequest, db: Session = Depends(get_db)):
    journal = db.query(models.JournalEntry).filter(models.JournalEntry.id == entry_id).first()
    if not journal:
        raise HTTPException(status_code=404, detail="Journal entry not found")

    db.query(models.WordEmotion).filter(models.WordEmotion.journal_id == journal.id).delete()

    dominant_emotion, dominant_score, all_emotions, word_emotions_data = analyze_emotions(request.text)
    journal.text = request.text
    journal.dominant_emotion = dominant_emotion
    journal.dominant_score = dominant_score
    journal.all_emotions = all_emotions
    journal.word_emotions = []

    for word in word_emotions_data:
        journal.word_emotions.append(models.WordEmotion(
            id=str(uuid4()),
            text=word['text'],
            emotion=word['emotion'],
            score=word['score']
        ))

    db.commit()
    db.refresh(journal)

    save_to_dynamodb({
        "id": journal.id,
        "text": journal.text,
        "date": journal.date.isoformat(),
        "dominant_emotion": dominant_emotion,
        "dominant_score": dominant_score,
        "all_emotions": all_emotions,
        "word_emotions": word_emotions_data
    })

    return {
        "id": journal.id,
        "text": journal.text,
        "date": journal.date,
        "dominant_emotion": dominant_emotion,
        "dominant_score": dominant_score,
        "all_emotions": all_emotions,
        "word_emotions": word_emotions_data
    }

@router.get("/journal-entry/by-date", response_model=JournalEntryResponse)
def get_journal_by_date(date_str: str = Query(...), db: Session = Depends(get_db)):
    try:
        date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD.")

    journal = db.query(models.JournalEntry).filter(models.JournalEntry.date == date_obj).first()
    if not journal:
        raise HTTPException(status_code=404, detail="No journal entry found for this date")

    return {
        "id": journal.id,
        "text": journal.text,
        "date": journal.date,
        "dominant_emotion": journal.dominant_emotion,
        "dominant_score": journal.dominant_score or 0.0,
        "all_emotions": journal.all_emotions or [],
        "word_emotions": [
            {"text": w.text, "emotion": w.emotion, "score": w.score}
            for w in journal.word_emotions
        ]
    }

@router.get("/journal-entries", response_model=List[JournalEntryResponse])
def get_all_journals(db: Session = Depends(get_db)):
    journals = db.query(models.JournalEntry).all()
    response = []
    for j in journals:
        entry = JournalEntryResponse(
            id=j.id,
            text=j.text,
            date=j.date,
            dominant_emotion=j.dominant_emotion,
            dominant_score=j.dominant_score or 0.0,
            all_emotions=j.all_emotions or [],
            word_emotions=[
                WordEmotionOut(
                    text=w.text,
                    emotion=w.emotion,
                    score=w.score
                )
                for w in j.word_emotions
            ]
        )
        response.append(entry)
    return response

from fastapi import APIRouter, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import httpx, os, difflib
from dotenv import load_dotenv
import boto3
from uuid import uuid4
from datetime import datetime

load_dotenv()
router = APIRouter()

# CORS setup (Configure this appropriately for your frontend)

# DynamoDB setup
dynamodb = boto3.resource("dynamodb", region_name="ap-south-1")
emotion_table = dynamodb.Table("UserEmotionLogs") # Optional table for emotion history
habit_table = dynamodb.Table("HabitFlowProgress") # Ensure this table is defined

# Base prompt
BASE_PROMPT = """
You are Lumi, a compassionate mental health support assistant. You help users who are feeling stressed, anxious, or overwhelmed.
You are not a medical professional and never offer clinical advice or diagnosis.
Always encourage users to reach out to licensed therapists or mental health hotlines if they are in crisis.
Keep your responses warm, empathetic, and supportive. Keep the responses concise and to the point preferrably not more than 2 sentences.
"""

# Request schema
class Message(BaseModel):
    user_input: str
    user_id: str = "demo_user"
    emotion: str = None
    stress: float = None
    risky_tweet: bool = False

def get_uncompleted_habits_today(user_id: str):
    today = datetime.utcnow().date().isoformat()
    pending_habits = []

    try:
        response = habit_table.scan()
        for item in response.get("Items", []):
            if item.get("user_id") == user_id and item.get("is_active", False):
                last_completed = item.get("last_completed", "")
                if last_completed != today:
                    pending_habits.append(item)

                    # Update last_completed so we don’t remind again today
                    # This logic updates the DB as soon as we fetch habits for reminder?
                    # Usually you update 'last_reminder_sent', but keeping your logic:
                    habit_table.update_item(
                        Key={"user_id": item["user_id"], "habit_id": item["habit_id"]},
                        UpdateExpression="SET last_completed = :today",
                        ExpressionAttributeValues={":today": today}
                    )
    except Exception as e:
        print(f"⚠️ Error fetching habits: {e}")

    return pending_habits

# Main chat route
@router.post("/chat")
async def chat(message: Message, request: Request):
    user_input = message.user_input.strip()
    user_id = message.user_id
    emotion = message.emotion
    stress = message.stress
    risky_tweet_text = message.risky_tweet

    print(f"🧠 User Input: {user_input}")
    print(f"🧠 Emotion: {emotion}, Stress Score: {stress}, Risky Tweet Text: {risky_tweet_text}")

    # ✅ Emotion log (optional)
    if emotion or stress is not None:
        try:
            emotion_table.put_item(Item={
                "user_id": user_id,
                "timestamp": datetime.utcnow().isoformat(),
                "emotion": emotion or "unknown",
                "stress": stress or 0.5,
                "message": user_input
            })
        except Exception as e:
            print(f"⚠️ Error logging emotion: {e}")

    # ✅ Habit encouragement flow (when not triggered by risky tweet)
    if not risky_tweet_text:
        pending_habits = get_uncompleted_habits_today(user_id)
        if pending_habits:
            habit_names = [h["habit_name"] for h in pending_habits]
            habit_list = ", ".join(habit_names)
            encouragement = (
                f"🌱 Just a gentle reminder — don't forget your healthy habits today: {habit_list}. "
                f"You’re doing great, keep going! 💪"
            )
            return {"response": encouragement}

    # 🧠 Tone scaffolding
    emotion_context = ""
    if risky_tweet_text:
        emotion_context += (
            "⚠️ The user may be at mental health risk based on their recent social media post. "
            "Respond with high empathy, but don’t be robotic. You may include a grounding exercise, gentle humor, or supportive encouragement if appropriate. "
            "Feel free to share one actionable tip (like deep breathing, journaling, or a distraction strategy). "
            "You can nudge them to talk to a mental health professional, but prioritize making them feel safe and understood.\n"
        )
    elif stress and stress > 0.7:
        emotion_context += (
            "🧘 The user seems highly stressed. Speak gently and offer helpful suggestions like relaxation techniques or supportive thoughts.\n"
        )
    elif emotion in ["sad", "angry", "fearful"]:
        emotion_context += f"The user feels {emotion}. Be affirming and avoid advice overload.\n"

    # Construct the full prompt for the RAG model
    # Note: The RAG server on Colab expects 'query' in the JSON body
    full_prompt = f"{BASE_PROMPT.strip()}\n\n{emotion_context}User: {user_input or risky_tweet_text}"

    # 💬 Make request to RAG server (running on Google Colab via Ngrok)
    # IMPORTANT: Update this URL every time you restart the Colab runtime
    # Make sure NOT to include a trailing slash (e.g., NO "/" at the end)
    COLAB_NGROK_URL = "https://braydon-unjudgable-lelia.ngrok-free.dev/" 
    
    # Remove trailing slash if accidentally added
    if COLAB_NGROK_URL.endswith("/"):
        COLAB_NGROK_URL = COLAB_NGROK_URL[:-1]

    try:
        async with httpx.AsyncClient() as client:
            # Trying '/query' first (Standard for RAG servers)
            target_url = f"{COLAB_NGROK_URL}/query"
            
            print(f"🚀 Sending request to: {target_url}")
            
            response = await client.post(
                target_url, 
                json={"query": full_prompt}, 
                timeout=90.0  # Generous timeout for RAG + Generation
            )
            
            # Fallback: If /query fails with 404, try /chat (older server versions)
            if response.status_code == 404:
                print("⚠️ /query not found, trying /chat endpoint...")
                target_url = f"{COLAB_NGROK_URL}/chat"
                response = await client.post(
                    target_url, 
                    json={"question": full_prompt}, # Note: /chat usually expects 'question', not 'query'
                    timeout=90.0
                )

            if response.status_code != 200:
                print(f"❌ RAG Server Error ({response.status_code}):", response.text)
                return {
                    "response": "😔 I’m having trouble reaching my thought center right now, but I’m still here for you. Want to try a simple breathing exercise together?"
                }
            
            data = response.json()
            # The Colab server returns {"answer": "..."} or {"response": "..."}
            reply = data.get("answer") or data.get("response") or "🤖 No valid response generated."
            return {"response": reply.strip()}

    except Exception as e:
        import traceback
        print("🔥 Exception in /chat:", str(e))
        traceback.print_exc()
        return {
            "response": "🚨 Connection error. You're not alone—I’m still right here. Let’s take it slow. Want a grounding tip?"
        }
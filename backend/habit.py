import boto3
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from dotenv import load_dotenv
import os
import requests
from fastapi.middleware.cors import CORSMiddleware
from ibm_watsonx_ai.credentials import Credentials
from ibm_watsonx_ai import APIClient
from ibm_watsonx_ai.foundation_models import ModelInference
from boto3.dynamodb.conditions import Key
from uuid import uuid4
from datetime import datetime
from decimal import Decimal
from uuid import UUID
import json


class HabitProgressInput(BaseModel):
    user_id: str
    habit_id: str
    habit_name: str
    replacement_habit: str
    streak: int
    level: int
    last_completed: str  # "YYYY-MM-DD"

class StreakUpdateInput(BaseModel):
    user_id: str
    habit_id: str


router = APIRouter()

dynamodb = boto3.resource("dynamodb", region_name="ap-south-1")  # change region if needed
table = dynamodb.Table("HabitFlowProgress")  # make sure this exists


load_dotenv()



API_KEY = os.getenv("WATSONX_API_KEY")
credentials = Credentials(
    url="https://eu-de.ml.cloud.ibm.com",  # or regional Watsonx URL
    api_key=os.getenv("WATSONX_API_KEY")
)
client = APIClient(credentials)

mistral_model = ModelInference(
    model_id="mistralai/mistral-medium-2505",  # ⚠️ A supported model with long-term viability
    credentials=credentials,
    project_id="1cb8c38f-d650-41fe-9836-86659006c090",
    params={"decoding_method": "greedy", "max_new_tokens": 100}
)

class HabitInput(BaseModel):
    bad_habit: str

@router.post("/suggest_replacements")
def suggest_replacements(data: HabitInput):
    try:
        prompt = (
        f"Suggest 3 healthy replacement habits for the bad habit: \"{data.bad_habit}\".\n"
        "Make each suggestion concise (max 5 words).\n"
        "Output the response as a JSON object with a single key 'suggestions' which contains a list of 3 strings."
    )

        response = mistral_model.generate(prompt)
        print(response)
        raw = response["results"][0]["generated_text"]

        start_index = raw.find('{')
        end_index = raw.rfind('}')

        if start_index != -1 and end_index != -1:
        # Extract the pure JSON substring
            clean_json_text = raw[start_index : end_index + 1]
        else:
        # If brackets aren't found, try to strip markdown fences if they exist
            clean_json_text = raw.replace("```json", "").replace("```", "").strip()
        
        data = json.loads(clean_json_text)


        suggestions = data.get("suggestions", [])
        return {"suggestions": suggestions[:3]}
    except Exception as e:
        print("🧨 Granite LLM Error:", str(e))
        return {"suggestions": ["Take a short walk", "Drink water", "Stretch mindfully"]}

@router.post("/habitflow/save-progress")
def save_progress(data: HabitProgressInput):
    habit_id = str(uuid4())
    table.put_item(Item={
        "user_id": data.user_id,
        "habit_id": habit_id,
        "habit_name": data.habit_name,
        "replacement_habit": data.replacement_habit,
        "streak_days": Decimal(str(data.streak)),
        "level": Decimal(str(data.level)),
        "started_on": datetime.now().date().isoformat(),
        "last_completed": data.last_completed,
        "is_active": True
    })
    return {"message": "✅ Habit progress saved separately!"}

@router.get("/habitflow/get-progress")
def get_habit_progress(user_id: str = None):
    try:
        if user_id:
            response = table.query(
                KeyConditionExpression=Key("user_id").eq(user_id)
            )
        else:
            response = table.scan()

        items = response.get("Items", [])
        return {"habits": items}
    except Exception as e:
        return {"error": str(e), "habits": []}
    

@router.post("/habitflow/increment-streak")
def increment_streak(data: StreakUpdateInput):
    try:
        response = table.get_item(Key={"user_id": data.user_id, "habit_id": data.habit_id})
        item = response.get("Item")
        if not item:
            return {"error": "Habit not found"}

        new_streak = item.get("streak_days", 0) + 1
        new_level = item.get("level", 0)
        if new_streak % 5 == 0:
            new_level += 1

        table.update_item(
            Key={"user_id": data.user_id, "habit_id": data.habit_id},
            UpdateExpression="SET streak_days = :sd, last_completed = :lc, #lvl = :lv",
            ExpressionAttributeNames={"#lvl": "level"},
            ExpressionAttributeValues={
                ":sd": Decimal(str(new_streak)),
                ":lc": datetime.now().date().isoformat(),
                ":lv": Decimal(str(new_level))
            }
        )
        return {"message": "✅ Day added, streak updated!"}
    except Exception as e:
        print("❌ Increment streak error:", str(e))
        return {"error": str(e)}

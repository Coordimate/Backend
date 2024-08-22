import os

from bson import ObjectId
import motor.motor_asyncio
from collections import defaultdict
from fastapi import WebSocket
from dotenv import load_dotenv


load_dotenv()
client = motor.motor_asyncio.AsyncIOMotorClient(os.environ["MONGODB_URL"])
db = client.coordimate
groups_collection = db.get_collection("groups")


class ConnectionManager:
    def __init__(self):
        self.active_connections: dict[str, dict[str, WebSocket]] = defaultdict(dict)

    async def connect(self, group_id: str, user_id: str, websocket: WebSocket):
        await websocket.accept()
        self.active_connections[group_id][user_id] = websocket
        await websocket.send_text('{}')

    def disconnect(self, group_id: str, user_id: str):
        try:
            self.active_connections[group_id].pop(user_id)
        except:
            pass

    async def broadcast(self, group_id: str, message: str):
        group_found = await groups_collection.find_one({"_id": ObjectId(group_id)})
        if group_found is None:
            return

        msgs = group_found.get('chat_messages', None)
        if not msgs or msgs == '[]':
            msgs = f"[{message}]"
        else:
            msgs = f"{msgs[:-1]},{message}]"

        await groups_collection.find_one_and_update(
            {"_id": ObjectId(group_id)},
            {"$set": {"chat_messages": msgs}},
        )

        for connection in self.active_connections[group_id].values():
            await connection.send_text(message)

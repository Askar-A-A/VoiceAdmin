from app.db.session import SessionLocal
from app.models.voicemail import VoiceMessage


db = SessionLocal()

vm = VoiceMessage(menu_id = 1, recording_sid = "ububsdbdbidni")

db.add(vm)
db.commit()

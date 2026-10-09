# Import every model so Base.metadata sees them (Alembic autogenerate, create_all).
from app.models.user import User
from app.models.audio import Folder, AudioFile
from app.models.ivr import IVRConfig, Menu
from app.models.calls import Call, CallLog
from app.models.voicemail import VoiceMessage
from app.models.conference import Conference

__all__ = [
    "User",
    "Folder",
    "AudioFile",
    "IVRConfig",
    "Menu",
    "Call",
    "CallLog",
    "VoiceMessage",
    "Conference",
]

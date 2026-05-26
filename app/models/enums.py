from enum import StrEnum


class UserRole(StrEnum):
    patient = "patient"
    doctor = "doctor"
    admin = "admin"


class AppointmentStatus(StrEnum):
    confirmed = "confirmed"
    cancelled = "cancelled"
    finished = "finished"


class Channel(StrEnum):
    web_chat = "web_chat"
    web_voice = "web_voice"
    phone = "phone"


class InteractionStatus(StrEnum):
    started = "started"
    in_progress = "in_progress"
    completed = "completed"
    abandoned = "abandoned"
    failed = "failed"


class SlotStatus(StrEnum):
    available = "available"
    held = "held"
    booked = "booked"
    cancelled = "cancelled"

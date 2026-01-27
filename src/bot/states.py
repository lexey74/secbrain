from aiogram.fsm.state import State, StatesGroup

class ContentStates(StatesGroup):
    """States for content handling flow"""
    waiting_description = State()
    waiting_title = State()
    waiting_comments_confirmation = State()
    waiting_url = State()

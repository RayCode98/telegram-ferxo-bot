from aiogram.fsm.state import State, StatesGroup


class Onboarding(StatesGroup):
    alias = State()
    birth_date = State()
    gender = State()
    seeking_gender = State()
    location = State()


class EditProfile(StatesGroup):
    bio = State()
    age_range = State()

from aiogram.fsm.state import State, StatesGroup


class Onboarding(StatesGroup):
    alias = State()
    birth_date = State()
    gender = State()
    seeking_gender = State()
    country = State()
    location = State()


class EditProfile(StatesGroup):
    alias = State()
    bio = State()
    photo = State()


class Preferences(StatesGroup):
    min_age = State()
    max_age = State()



class GrowthStates(StatesGroup):
    home_country = State()
    travel_country = State()

import json
import random
from time import perf_counter
from enum import IntEnum


class BombPartyPlayer:
    def __init__(self, user, lives):
        self.user = user
        self.lives = lives

    @property
    def dead(self):
        return self.lives == 0

    def __str__(self):
        return f"{self.user} ({'♥'*self.lives})"


class BombParty:
    valid_bomb_settings = {
        "difficulty": ("easy", "medium", "hard", "nightmare", "impossible"),
        "timer": range(5, 60 + 1),
        "minimum_time": range(0, 10 + 1),
        "lives": range(1, 5 + 1),
    }

    in_progress: bool
    started: bool
    used_words: list
    party: dict
    current_player_index: int
    current_letters: str
    bomb_start_time: float
    turn_order: list
    timer: int
    bomb_settings: dict

    def __init__(self):
        self.bomb_party_letters = self.construct_bomb_party_letters()
        self.set_default_values()

        self.bomb_setting_functions = {
            "lives": self.on_lives_set,
        }

    @property
    def default_settings(self):
        return {
            "difficulty": "medium",
            "timer": 30,
            "minimum_time": 5,
            "lives": 3,
        }

    def set_default_values(self):
        self.in_progress = False
        self.started = False
        self.used_words = []
        self.party = {}
        self.current_player_index = 0
        self.current_letters = ""
        self.bomb_start_time = 0
        self.turn_order = []
        self.timer = 30
        self.bomb_settings = self.default_settings

    @staticmethod
    def construct_bomb_party_letters():
        with open("data/2strings.json", "r") as f:
            letters = json.load(f)
            with open("data/3strings.json", "r") as f3:
                letters.update(json.load(f3))

            return {
                "easy": [let for let, amount in letters.items() if amount >= 10000 and '-' not in let],
                "medium": [let for let, amount in letters.items() if 10000 > amount >= 5000 and '-' not in let],
                "hard": [let for let, amount in letters.items() if
                         5000 > amount >= 1000 or (amount >= 5000 and '-' in let)],
                "nightmare": [let for let, amount in letters.items() if 1000 > amount >= 500],
                "impossible": [let for let, amount in letters.items() if 500 > amount],
            }

    def add_player(self, user):
        if user not in self.party:
            self.party.update({user: BombPartyPlayer(user, self.bomb_settings['lives'])})

    def remove_player(self, user):
        if user in self.party:
            if self.started:
                self.party[user].lives = 0
            else:
                del self.party[user]

    def on_in_progress(self):
        self.in_progress = True

    def on_start(self):
        self.turn_order = list(self.party.keys())
        random.shuffle(self.turn_order)
        self.timer = self.bomb_settings['timer']
        self.bomb_start_time = perf_counter()
        self.started = True

    def on_word_used(self, message):
        message = message.lower()
        self.timer -= max((0, perf_counter() - self.bomb_start_time - self.bomb_settings['minimum_time']))
        self.used_words.append(message)

    def on_explode(self):
        self.timer = self.bomb_settings['timer']
        self.bomb_start_time = 0
        player = self.current_player
        player.lives -= 1
        return f"@{player.user} " + \
               (f"You ran out of time and now have {player.lives} {'♥' * player.lives} heart(s) left"
                if player.lives != 0 else "You ran out of time and lost all your lives! YouDied")

    def on_close(self):
        self.set_default_values()

    def next_player(self):
        player = self.current_player.user
        while self.current_player.lives == 0 or self.current_player.user == player:
            self.current_player_index = 1 + self.current_player_index if self.current_player_index != len(self.turn_order) - 1 else 0
        self.bomb_start_time = perf_counter()

    def set_letters(self):
        self.current_letters = random.choice(self.bomb_party_letters[self.bomb_settings['difficulty']])

    def get_winner(self):
        players_left = [player for player in self.party.values() if player.lives != 0]
        return players_left[0] if len(players_left) == 1 else None

    def set_setting(self, setting, value):
        if setting not in self.bomb_settings:
            return f"That's not a valid setting. Valid settings: {', '.join(list(self.bomb_settings.keys()))}"
        try:
            value = type(self.bomb_settings[setting])(value)
            if value not in self.valid_bomb_settings[setting]:
                return "That's not a valid value for this setting."
            self.bomb_settings[setting] = value
            if setting in self.bomb_setting_functions:
                self.bomb_setting_functions[setting]()
            return f"The {setting} setting has been changed to {value}"
        except ValueError:
            return "There was a problem processing the value you gave for the specific setting."

    def on_lives_set(self):
        for player in self.party:
            self.party[player].lives = self.bomb_settings['lives']

    def check_message(self, message):
        message = message.lower()
        if message in self.used_words:
            return "That word has already been used."
        if self.current_letters not in message:
            return f"That word does not contain your string of letters: {self.current_letters}"
        if len(message) == len(self.current_letters):
            return "You cannot answer with the string of letters itself."

    @property
    def current_player(self):
        if len(self.turn_order) == 0:
            return None
        return self.party[self.turn_order[self.current_player_index]]

    @property
    def player_list(self):
        return list(self.party.values())

    @property
    def can_start(self):
        return len(self.party) >= 2

    @property
    def host(self):
        return list(self.party.keys())[0]

    @property
    def winning_money(self):
        return len(self.party) * 100

    @property
    def seconds_left(self):
        return self.timer+self.bomb_settings['minimum_time']

    @property
    def starting_time(self):
        return self.timer + self.bomb_settings['minimum_time']

    @property
    def valid_settings_string(self):
        return ", ".join(list(self.valid_bomb_settings.keys()))


class ScrambleHintType(IntEnum):
    DEFAULT = 0
    EVERY_OTHER = 1


class Scramble:
    banned_words = [
        # Was originally used to stop this word from being posted for scramble, but since there's a new list with non-tos words it doesn't really do anything
        "kike"
    ]

    def __init__(self, name, answer_generator, difficulty_multiplier=1, hint_type=ScrambleHintType.DEFAULT, case_sensitive=False):
        self.name = name
        self.difficulty_multiplier = difficulty_multiplier
        self.hint_type = hint_type
        self.case_sensitive = case_sensitive

        self.answer = None
        self.hint = ""
        self.future = None

        setattr(self, "generate_answer", answer_generator)

    def reset(self):
        self.answer = None
        self.hint = ""
        if self.future is not None and not self.future.cancelled() and not self.future.done():
            self.future.cancel()
        self.future = None

    def new_answer(self, channel):
        args = []
        if self.generate_answer.__code__.co_argcount > 0:  # Check whether it takes the channel arg
            args.append(channel)
        self.answer = self.generate_answer(*args)
        count = 0
        while self.answer in self.banned_words:
            self.answer = self.generate_answer(*args)
            count += 1
            if count > 100:  # Just in case ig
                raise Exception("Could not generate an unbanned answer")
        self.hint = "?" * len(self.answer)

    def update_hint(self):
        getattr(self, f"{self.hint_type.name.lower()}_hint")()
        return self.hint

    def default_hint(self):
        i = self.hint.index("?")
        self.hint = self.hint[:i] + self.answer[i] + (len(self.answer) - i - 1) * "?"

    def every_other_hint(self):
        try:
            i = self.hint.index("??") + 1
            self.hint = self.hint[:i] + self.answer[i] + (len(self.answer) - i - 1) * "?"
        except ValueError:  # ValueError thrown when no "??" in hint, so use default hint.
            self.default_hint()

    @property
    def hints_left(self):
        return "?" in self.hint

    @property
    def in_progress(self):
        return self.answer is not None


class ScrambleManager:
    def __init__(self, scrambles):
        self.scrambles = scrambles

    def in_progress(self, identifier):
        return self.scrambles[identifier].in_progress

    def hints_left(self, identifier):
        return self.scrambles[identifier].hints_left

    def get_scramble(self, identifier, channel):
        self.scrambles[identifier].new_answer(channel)
        scrambled_word = [char for char in self.scrambles[identifier].answer]
        random.shuffle(scrambled_word)
        return "".join(scrambled_word)

    def get_hint(self, identifier):
        return self.scrambles[identifier].update_hint()

    def get_scramble_name(self, identifier):
        return self.scrambles[identifier].name

    def get_answer(self, identifier):
        return self.scrambles[identifier].answer

    def check_answer(self, identifier, guess):
        scramble = self.scrambles[identifier]
        if (guess.lower() == scramble.answer.lower() and not scramble.case_sensitive) or guess == scramble.answer:
            return round(
                random.randint(5, 10) *
                len(scramble.answer.replace(" ", "")) *
                scramble.hint.count("?")/len(scramble.answer) *
                scramble.difficulty_multiplier
            )

    def reset(self, identifier):
        self.scrambles[identifier].reset()

    def pass_future(self, identifier, future):
        self.scrambles[identifier].future = future


class Trivia:
    def __init__(self):
        pass
class WTCombotError(Exception):
    def __init__(self, error_message):
        self.__error_message = error_message
    def get_message(self):
        return self.__error_message
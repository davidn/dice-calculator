#!/usr/bin/env python3


class UnfulfillableRequestError(Exception):
    pass


class RecognitionError(UnfulfillableRequestError):
    pass


class ImpossibleSpellError(UnfulfillableRequestError):
    pass


class ImpossibleDiceError(UnfulfillableRequestError):
    pass

"""Shared type definitions for BDG Predictor.""" 

from typing import TypedDict, NotRequired

class DrawRowDict(TypedDict):
    period: str
    number: int
    color: str

class PredictionBlockDict(TypedDict):
    number: int
    color: str
    size: str
    accuracy: str
    accuracy_value: float

class PredictionDict(TypedDict):
    timestamp: str
    next_period: str
    primary_prediction: PredictionBlockDict
    alternative_prediction: NotRequired[PredictionBlockDict]
    backup_prediction: NotRequired[PredictionBlockDict]
    strong_possibility: NotRequired[PredictionBlockDict]
    trend_analysis: dict[str, str]
    summary: dict[str, str]

class StatusDict(TypedDict):
    status: str
    error: NotRequired[str]
    service: NotRequired[str]
    timestamp: NotRequired[str]

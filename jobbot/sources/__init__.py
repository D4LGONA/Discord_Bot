"""수집 소스 레지스트리."""

from .base import Source
from .gamejob import GameJob
from .jobkorea import JobKorea
from .saramin import Saramin
from .wanted import Wanted

REGISTRY = {
    "gamejob": GameJob,
    "wanted": Wanted,
    "saramin": Saramin,
    "jobkorea": JobKorea,
}

__all__ = ["Source", "REGISTRY", "GameJob", "Wanted", "Saramin", "JobKorea"]

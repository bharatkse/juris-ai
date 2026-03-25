"""
User management APIs.
"""

from fastapi import APIRouter

from src.core.constants import API_V1_PREFIX
from src.core.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix=API_V1_PREFIX, tags=["Users"])

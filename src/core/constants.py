from http import HTTPStatus

# ------------------------------------------------------------------
# Error codes (API-level, stable contracts)
# ------------------------------------------------------------------
ERROR_INTERVAL_SERVER_ERROR = "INTERNAL_SERVER_ERROR"
ERROR_DOMAIN = "DOMAIN_ERROR"
ERROR_NOT_FOUND = "NOT_FOUND"
ERROR_PERSISTENCE = "PERSISTENCE_ERROR"
ERROR_UNHANDLED = "UNHANDLED_EXCEPTION"
ERROR_BAD_REQUEST = "BAD_REQUEST"
ERROR_UNPROCESSABLE_ENTITY = "UNPROCESSABLE_ENTITY"

# ------------------------------------------------------------------
# Common HTTP statuses (optional but explicit)
# ------------------------------------------------------------------

HTTP_400_BAD_REQUEST = HTTPStatus.BAD_REQUEST
HTTP_404_NOT_FOUND = HTTPStatus.NOT_FOUND
HTTP_500_INTERNAL_SERVER_ERROR = HTTPStatus.INTERNAL_SERVER_ERROR
HTTP_200_OK = HTTPStatus.OK
HTTP_201_CREATED = HTTPStatus.CREATED
HTTP_202_ACCEPTED = HTTPStatus.ACCEPTED
HTTP_204_NO_CONTENT = HTTPStatus.NO_CONTENT
HTTP_422_UNPROCESSABLE_ENTITY = HTTPStatus.UNPROCESSABLE_ENTITY

# ------------------------------------------------------------------
# API
# ------------------------------------------------------------------
API_V1_PREFIX = "/api/v1"


# ------------------------------------------------------------------
# Pagination defaults
# ------------------------------------------------------------------

DEFAULT_PAGE = 1
DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100

# ------------------------------------------------------------------
# Application defaults
# ------------------------------------------------------------------
DEFAULT_APP_NAME = "juris-ai"
DEFAULT_APP_VERSION = "1.0.0"

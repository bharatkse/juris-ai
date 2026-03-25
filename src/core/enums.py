from enum import StrEnum


class ConnectivityStatus(StrEnum):
    online = "online"
    offline = "offline"


class StationSortField(StrEnum):
    score = "score"
    created = "created"
    updated = "updated"


class SortOrder(StrEnum):
    asc = "asc"
    desc = "desc"

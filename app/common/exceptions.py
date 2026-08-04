class DogMapError(Exception):
    """모든 도메인 예외의 공통 베이스."""


class NotFoundError(DogMapError):
    def __init__(self, resource: str, identifier: object):
        self.resource = resource
        self.identifier = identifier
        super().__init__(f"{resource} not found: {identifier}")


class AlreadyExistsError(DogMapError):
    def __init__(self, resource: str, identifier: object):
        self.resource = resource
        self.identifier = identifier
        super().__init__(f"{resource} already exists: {identifier}")

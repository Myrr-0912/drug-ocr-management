from fastapi import HTTPException, status


class NotFoundError(HTTPException):
    def __init__(self, detail: str = "资源不存在"):
        super().__init__(status_code=status.HTTP_404_NOT_FOUND, detail=detail)


class UnauthorizedError(HTTPException):
    def __init__(self, detail: str = "未认证，请先登录"):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
            headers={"WWW-Authenticate": "Bearer"},
        )


class ForbiddenError(HTTPException):
    def __init__(self, detail: str = "权限不足"):
        super().__init__(status_code=status.HTTP_403_FORBIDDEN, detail=detail)


class ConflictError(HTTPException):
    def __init__(self, detail: str = "数据冲突"):
        super().__init__(status_code=status.HTTP_409_CONFLICT, detail=detail)


class BusinessError(HTTPException):
    def __init__(self, detail: str = "业务处理失败"):
        super().__init__(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)

from typing import TYPE_CHECKING, Any, Type, Callable
from functools import wraps


class FakePaginationParameters:
    """Fake class of PaginationParameters from flask-smorest as their typing don't work.

    :param int page: Page number
    :param int page_size: Page size
    """

    def __init__(self, page: int, page_size: int) -> None:
        self.page = page
        self.page_size = page_size
        self.item_count: int|None = None

    @property
    def first_item(self) -> int:
        """Return first item number"""
        return (self.page - 1) * self.page_size

    @property
    def last_item(self) -> int:
        """Return last item number"""
        return self.first_item + self.page_size - 1

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}"
            f"(page={self.page!r},page_size={self.page_size!r})"
        )


def sogo_collection_query(page: int = None, page_size: int = None, max_page_size: int = None, sort: bool = False, filter: bool = False) -> Callable:
    """
    Decorator for pagination

    :param page: _description_, defaults to None
    :type page: _type_, optional
    :param page_size: _description_, defaults to None
    :type page_size: _type_, optional
    :param max_page_size: _description_, defaults to None
    :type max_page_size: _type_, optional
    """

    # Pagination
    if page is None:
        page = 1
    if page_size is None:
        page_size = 10
    if max_page_size is None:
        max_page_size = 100


    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            print("Hello start")

            ret = func(*args, **kwargs)

            print("Hello after")

            return ret
        

        
        return wrapper

    return decorator



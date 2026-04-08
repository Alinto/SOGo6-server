from functools import wraps
from collections.abc import Callable
from typing import Any, Type

from json import dumps

from flask import make_response, jsonify, request
from flask_smorest import Blueprint
from marshmallow import Schema, fields as ma_fields, validate, EXCLUDE, post_load, validates_schema
from webargs.flaskparser import FlaskParser

# Return type for functions decorated with @collection_paginate.
# The decorated function must return a tuple of (item_count, response_body, status_code).
CustomPaginateResponse = tuple[int, dict, int]

class CollectionPaginateArgs:
    """
    Simple class that has all custome paginate args
    """
    def __init__(self, page:int,
                 page_size:int,
                 sort_by:str|None = None,
                 sort_order:str|None = None,
                 fields:str|None = None,
                 fields_action:str|None = None):
        self.page = page
        self.page_size = page_size
        self.sort_by = sort_by
        self.sort_order = sort_order
        self.fields = fields
        self.fields_action = fields_action

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
            f"Collection Pagination args"
            f"(page={self.page},page_size={self.page_size})"
            f"(sort_by={self.sort_by},sort_order={self.sort_order})"
            f"(fields={self.fields},fields_action={self.fields_action})"
        )

def collection_pagination_parameters(def_max_page_size:int, can_sort:bool, sort_value_set:set|None,
                                     can_filter:bool, filter_value_set:set|None) -> Type[Schema]:
    """Generate a PaginationParametersSchema"""

    class CollectionPaginationParametersSchema(Schema):
        """Deserializes pagination params into PaginationParameters"""

        class Meta:
            """Set behavior for unknwon param"""
            unknown = EXCLUDE

        #Pagination
        page = ma_fields.Integer(load_default=1, validate=validate.Range(min=1))
        page_size = ma_fields.Integer(load_default=20, validate=validate.Range(min=1, max=def_max_page_size))

        #Sorting
        if can_sort:
            if sort_value_set:
                meta_sort = f"You can sort by one of those: {sort_value_set}"
            else:
                meta_sort = "Define the param you want to sort by"
            sort_by = ma_fields.String(metadata={"description": meta_sort})
            sort_order = ma_fields.String(load_default="asc", validate=validate.OneOf(["asc", "desc"]))

        #Filtering
        if can_filter:
            if filter_value_set:
                meta_field = f"Comma separated list of fields among: {filter_value_set}"
            else:
                meta_field = "Comma separated list of fields (ex: fields=uid,subject)"
            fields = ma_fields.String(metadata={"description": meta_field}) # type: ignore[assignment]
            fields_action = ma_fields.String(load_default="include", validate=validate.OneOf(["include", "exclude"]),
                                             metadata={"description": "Include those fields and excluse the others OR exclude those fields and include the others"})

        @validates_schema
        def check_sort_and_fields(self, data: dict, **kwargs: dict) -> None:
            """
            Check value fo sort_by and fields if necessary.
            For now, no ValidationError is raise if a value is not ok.
            """
            if can_sort and "sort_by" in data and sort_value_set:
                if data["sort_by"] not in sort_value_set:
                    #If the value is not expected, remove it so the params are clean
                    data.pop("sort_by")
                    data.pop("sort_order", None)

            if can_filter and "fields" in data and filter_value_set:
                true_field_list: list[str] = []
                for field in data["fields"].split(","):
                    if field in filter_value_set:
                        true_field_list.append(field)
                if true_field_list:
                    data["fields"] = ",".join(true_field_list)
                else:
                    data.pop("fields")
                    data.pop("fields_action", None)

        @post_load
        def make_paginator(self, data: dict, **kwargs: dict) -> CollectionPaginateArgs:
            """
            Return the object instead of a dict

            :rtype: CollectionPaginateArgs
            """
            return CollectionPaginateArgs(**data)

    return CollectionPaginationParametersSchema



class PaginationMetadataSchema(Schema):
    """Pagination metadata schema

    Used to serialize pagination metadata.
    Its main purpose is to document the pagination metadata.
    """

    total = ma_fields.Integer()
    total_pages = ma_fields.Integer()
    first_page = ma_fields.Integer()
    last_page = ma_fields.Integer()
    page = ma_fields.Integer()
    previous_page = ma_fields.Integer()
    next_page = ma_fields.Integer()

def make_pagination_metadata(page:int, page_size:int, item_count:int) -> dict:
    """Build pagination metadata from page, page size and item count

    Override this to use another pagination metadata structure
    """
    page_metadata = {}
    page_metadata["total"] = item_count
    if item_count == 0:
        page_metadata["total_pages"] = 0
    else:
        # First / last page, page count
        page_count = ((item_count - 1) // page_size) + 1
        first_page = 1
        last_page = page_count
        page_metadata["total_pages"] = page_count
        page_metadata["first_page"] = first_page
        page_metadata["last_page"] = last_page
        # Page, previous / next page
        if page <= last_page:
            page_metadata["page"] = page
            if page > first_page:
                page_metadata["previous_page"] = page - 1
            if page < last_page:
                page_metadata["next_page"] = page + 1
    return PaginationMetadataSchema().dump(page_metadata)

def collection_paginate(blp: Blueprint, max_page_size:int=None,
                        can_sort:bool=True, sort_value_set:set|None = None,
                        can_filter:bool=True, filter_value_set:set|None = None,) -> Callable:
    """
    Add parameters to query for pagination with sorting, filtering

    :param blp: _description_
    :type blp: Blueprint
    :param pagination_schema: _description_, defaults to None
    :type pagination_schema: type[Schema] | None, optional
    :return: _description_
    :rtype: Callable
    """

    flask_parser = FlaskParser()

    if max_page_size is None or max_page_size < 1:
        max_page_size = 100 #TODO make this default value configurable somewhere ??

    collection_schema = collection_pagination_parameters(max_page_size, can_sort, sort_value_set, can_filter, filter_value_set)

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            collection_param: CollectionPaginateArgs = flask_parser.parse(
                    collection_schema, request, location="query"
                )

            kwargs["collection_param"] = collection_param

            item_count, response, status_code = func(*args, **kwargs)

            # Si response est un dict, on le retourne avec le status_code
            response = make_response(jsonify(response), status_code)
            if item_count:
                response.headers["X-Pagination"] = dumps(
                make_pagination_metadata(
                    collection_param.page, collection_param.page_size, item_count
                ))
            return response

        wrapped = blp.arguments(collection_pagination_parameters(max_page_size, can_sort, sort_value_set, can_filter, filter_value_set),
                                location="query", arg_name="collection_param")(wrapper)
        return wrapped
    return decorator

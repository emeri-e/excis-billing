#!/usr/bin/env python3
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger


class CustomPaginator:
    """Custom paginator to handle paginated queryset results.

    Attributes:
        queryset (QuerySet): The list or queryset to paginate.
        page (int): Current page number.
        per_page (int): Number of items per page.
    """

    def __init__(self, queryset, page: int = 1, per_page: int = 10):
        """Initialize the paginator.

        Args:
            queryset (QuerySet): The data to paginate.
            page (int, optional): Page number. Defaults to 1.
            per_page (int, optional): Items per page. Defaults to 10.
        """
        self.queryset = queryset
        self.page = page
        self.per_page = per_page
        self.paginator = Paginator(self.queryset, self.per_page)

    def get_paginated_response(self):
        """Returns paginated data and metadata.

        Returns:
            dict: Contains paginated items and pagination info.
        """
        try:
            page_obj = self.paginator.page(self.page)
        except PageNotAnInteger:
            page_obj = self.paginator.page(1)
        except EmptyPage:
            page_obj = self.paginator.page(self.paginator.num_pages)

        return {
            "count": self.paginator.count,
            "total_pages": self.paginator.num_pages,
            "current_page": page_obj.number,
            "has_next": page_obj.has_next(),
            "has_previous": page_obj.has_previous(),
            "results": list(page_obj.object_list.values()) 
        }

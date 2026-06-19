from rest_framework.pagination import CursorPagination
from rest_framework.viewsets import ReadOnlyModelViewSet


class StandardCursorPagination(CursorPagination):
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 10
    ordering = '-id'


class BaseReadViewSet(ReadOnlyModelViewSet):
    pagination_class = StandardCursorPagination
    http_method_names = ['get']

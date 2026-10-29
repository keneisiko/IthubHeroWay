from rest_framework import serializers, views
from rest_framework.response import Response

from apps.accounts.permissions import IsKnownRole

from .models import News

NEWS_LIMIT = 10


class NewsSerializer(serializers.ModelSerializer):
    class Meta:
        model = News
        fields = ("id", "title", "body", "link", "published_at")


class NewsListView(views.APIView):
    permission_classes = [IsKnownRole]

    def get(self, request, *args, **kwargs):
        rows = News.objects.filter(is_published=True).order_by("-published_at")[:NEWS_LIMIT]
        return Response(NewsSerializer(rows, many=True).data)

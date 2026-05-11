from rest_framework import serializers

from .models import Quest, QuestRewardTransaction, UserQuestProgress


class QuestSerializer(serializers.ModelSerializer):
    class Meta:
        model = Quest
        fields = [
            "id",
            "code",
            "title",
            "description",
            "quest_type",
            "reward_coins",
            "reward_rating_delta",
            "conditions",
            "is_active",
            "start_at",
            "end_at",
        ]


class UserQuestProgressSerializer(serializers.ModelSerializer):
    quest = QuestSerializer(read_only=True)

    class Meta:
        model = UserQuestProgress
        fields = [
            "id",
            "quest",
            "progress_value",
            "is_completed",
            "completed_at",
            "proof_payload",
            "updated_at",
        ]


class UpdateQuestProgressSerializer(serializers.Serializer):
    progress_value = serializers.FloatField(min_value=0, required=False)
    proof_payload = serializers.JSONField(required=False)


class CompleteQuestSerializer(serializers.Serializer):
    proof_payload = serializers.JSONField(required=False)


class QuestRewardTransactionSerializer(serializers.ModelSerializer):
    quest_code = serializers.CharField(source="quest.code", read_only=True)
    quest_title = serializers.CharField(source="quest.title", read_only=True)

    class Meta:
        model = QuestRewardTransaction
        fields = [
            "id",
            "quest_code",
            "quest_title",
            "coins_delta",
            "rating_delta",
            "granted_at",
        ]


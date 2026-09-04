from __future__ import annotations

from django.contrib import admin, messages
from django.contrib.admin.models import ADDITION, CHANGE, LogEntry
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone
from django.utils.html import format_html

from apps.notifications.services import events
from apps.operations.admin_rbac import ManagedRoleAdminMixin, is_curator, is_hq, is_superadmin, is_tutor
from apps.quests.services.quest_completion import complete_quest_idempotent

from .models import (
    Quest,
    QuestRewardTransaction,
    QuestTemplate,
    SeasonalEvent,
    SelfReportProof,
    SelfReportProofStatus,
    SquadLeaderboardSnapshot,
    UserQuestProgress,
)


def _complete_quest_idempotent(user, quest, reviewer):
    progress, created = complete_quest_idempotent(
        user,
        quest,
        reason=f"Квест подтверждён куратором: {quest.code}",
    )
    LogEntry.objects.log_action(
        user_id=reviewer.pk,
        content_type_id=ContentType.objects.get_for_model(UserQuestProgress).pk,
        object_id=progress.pk,
        object_repr=str(progress),
        action_flag=CHANGE,
        change_message=f"Self-report approve for quest {quest.code}. reward_created={created}",
    )


@admin.register(QuestTemplate)
class QuestTemplateAdmin(ManagedRoleAdminMixin):
    list_display = ("code", "title", "quest_type", "verifier", "reward_coins", "is_active")
    list_filter = ("quest_type", "verifier", "is_active")
    search_fields = ("code", "title")

    def has_module_permission(self, request):
        return super().has_module_permission(request) and (
            request.user.is_superuser or request.user.role in {"admin", "curator", "tutor", "hq"}
        )


@admin.register(Quest)
class QuestAdmin(ManagedRoleAdminMixin):
    list_display = ("code", "title", "quest_type", "reward_coins", "reward_rating_delta", "is_active")
    list_filter = ("quest_type", "is_active", "start_at", "end_at")
    search_fields = ("code", "title")

    def has_module_permission(self, request):
        return super().has_module_permission(request) and (request.user.is_superuser or request.user.role in {"admin", "curator", "tutor", "hq"})


@admin.register(UserQuestProgress)
class UserQuestProgressAdmin(ManagedRoleAdminMixin):
    list_display = ("user", "quest", "progress_value", "is_completed", "updated_at")
    list_filter = ("is_completed", "quest__quest_type", "updated_at")
    search_fields = ("user__callsign", "user__username", "quest__code", "quest__title")

    def get_queryset(self, request):
        qs = super().get_queryset(request).select_related("user", "user__squad", "quest")
        if request.user.is_superuser or request.user.role == "admin":
            return qs
        if is_curator(request.user) and request.user.squad_id:
            return qs.filter(user__squad_id=request.user.squad_id)
        if is_tutor(request.user):
            return qs.filter(user__squad__course__gte=2, user__squad__course__lte=4)
        return qs.none()

    def has_module_permission(self, request):
        return super().has_module_permission(request) and not is_hq(request.user)


@admin.register(QuestRewardTransaction)
class QuestRewardTransactionAdmin(ManagedRoleAdminMixin):
    list_display = ("user", "quest", "coins_delta", "rating_delta", "granted_at")
    list_filter = ("granted_at",)
    search_fields = ("user__callsign", "quest__code")

    def has_module_permission(self, request):
        return super().has_module_permission(request) and not is_hq(request.user)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser


@admin.register(SeasonalEvent)
class SeasonalEventAdmin(ManagedRoleAdminMixin):
    list_display = ("code", "title", "progress_percent", "is_active", "started_at", "ended_at")
    list_filter = ("is_active", "started_at", "ended_at")
    search_fields = ("code", "title")
    actions = ("activate_season_operation",)

    @admin.action(description="Штаб: активировать сезонную операцию")
    def activate_season_operation(self, request, queryset):
        if not is_hq(request.user) and not is_superadmin(request.user):
            self.message_user(request, "Действие доступно только штабу.", level=messages.ERROR)
            return
        template = queryset.order_by("id").first()
        if not template:
            self.message_user(request, "Выберите шаблон сезонной операции.", level=messages.ERROR)
            return
        seasonal_event = SeasonalEvent.objects.create(
            code=f"{template.code}-run-{timezone.now().strftime('%Y%m%d%H%M%S')}",
            title=template.title,
            description=template.description,
            progress_percent=0,
            is_active=True,
            started_at=timezone.now(),
            ended_at=template.ended_at,
        )
        LogEntry.objects.log_action(
            user_id=request.user.pk,
            content_type_id=ContentType.objects.get_for_model(SeasonalEvent).pk,
            object_id=seasonal_event.pk,
            object_repr=str(seasonal_event),
            action_flag=ADDITION,
            change_message="Активирована сезонная операция из шаблона.",
        )
        self.message_user(request, f"Сезонная операция '{seasonal_event.title}' активирована.", level=messages.SUCCESS)


@admin.register(SquadLeaderboardSnapshot)
class SquadLeaderboardSnapshotAdmin(ManagedRoleAdminMixin):
    list_display = ("squad", "avg_rating", "agents_count", "captured_at")
    list_filter = ("captured_at", "squad")
    search_fields = ("squad__code", "squad__name")

    def has_module_permission(self, request):
        return super().has_module_permission(request) and not is_hq(request.user)

    def has_add_permission(self, request):
        return request.user.is_superuser or request.user.role in {"admin", "hq"}


@admin.register(SelfReportProof)
class SelfReportProofAdmin(ManagedRoleAdminMixin):
    list_display = ("user", "quest", "status_badge", "proof_link", "created_at", "reviewed_at")
    list_filter = ("status", "created_at", "quest__quest_type")
    search_fields = ("user__username", "user__email", "comment", "attachment_link")
    readonly_fields = ("created_at", "reviewed_at", "reviewed_by", "proof_link")
    actions = ("approve_proofs", "reject_proofs")

    @admin.display(description="Доказательство")
    def proof_link(self, obj: SelfReportProof):
        """Ссылка кликабельна прямо из списка.

        Куратор одобряет пачками; если ради проверки ссылки нужно открывать
        каждую заявку, проверять перестанут вовсе.
        """
        if not obj.attachment_link:
            return "—"
        return format_html(
            '<a href="{}" target="_blank" rel="noopener noreferrer">открыть</a>', obj.attachment_link
        )

    @admin.display(description="Статус")
    def status_badge(self, obj: SelfReportProof):
        if obj.status == SelfReportProofStatus.APPROVED:
            return format_html('<span style="color:#16a34a;font-weight:700;">Одобрен</span>')
        if obj.status == SelfReportProofStatus.REJECTED:
            return format_html('<span style="color:#dc2626;font-weight:700;">Отклонён</span>')
        return format_html('<span style="color:#ca8a04;font-weight:700;">На проверке</span>')

    def has_module_permission(self, request):
        # HQ must not see self-reports
        return super().has_module_permission(request) and not is_hq(request.user)

    def get_queryset(self, request):
        # Правило видимости живёт в одном месте: счётчик на главной и список
        # в админке обязаны показывать одно и то же.
        from apps.operations.services.review_queue import reviewable_proofs

        allowed = reviewable_proofs(request.user).values("pk")
        return (
            super()
            .get_queryset(request)
            .filter(pk__in=allowed)
            .select_related("user", "user__squad", "quest", "quest_progress")
        )

    @admin.action(description="Одобрить: начислить награду за квест")
    def approve_proofs(self, request, queryset):
        if is_hq(request.user):
            self.message_user(request, "Штаб не проверяет подтверждения.", level=messages.ERROR)
            return
        now = timezone.now()
        updated = 0
        for proof in queryset.select_related("quest", "user", "quest_progress"):
            if proof.status == SelfReportProofStatus.APPROVED:
                continue
            # Mark approved
            proof.status = SelfReportProofStatus.APPROVED
            proof.reviewed_by = request.user
            proof.reviewed_at = now
            proof.save(update_fields=["status", "reviewed_by", "reviewed_at"])
            _complete_quest_idempotent(proof.user, proof.quest, request.user)
            events.proof_reviewed(proof, approved=True)
            updated += 1
        self.message_user(request, f"Одобрено: {updated}", level=messages.SUCCESS)

    @admin.action(description="Отклонить: награда не начисляется")
    def reject_proofs(self, request, queryset):
        if is_hq(request.user):
            self.message_user(request, "Штаб не проверяет подтверждения.", level=messages.ERROR)
            return
        now = timezone.now()
        rejected = list(
            queryset.exclude(status=SelfReportProofStatus.REJECTED).select_related("user", "quest")
        )
        updated = queryset.exclude(status=SelfReportProofStatus.REJECTED).update(
            status=SelfReportProofStatus.REJECTED, reviewed_by=request.user, reviewed_at=now
        )
        for proof in rejected:
            events.proof_reviewed(proof, approved=False)
        self.message_user(request, f"Отклонено: {updated}", level=messages.SUCCESS)

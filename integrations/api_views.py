"""The upstream-facing endpoints (design 11.6, 11.7)."""

from __future__ import annotations

import csv

from django.db import transaction
from django.http import HttpResponse
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema

from integrations.api import (
    ApiError,
    SignedApiView,
    data_response,
    isoformat,
    list_response,
)
from integrations.pagination import paginate
from integrations.sanitize import clean_html
from integrations.serializers import (
    apply_fields,
    log_data,
    member_data,
    registration_data,
    team_data,
    tournament_data,
)
from tournaments.models import (
    ACTIVE_STATUSES,
    ActorType,
    Registration,
    RegistrationStatus,
    ReviewMode,
    Tournament,
    TournamentStatus,
)

BATCH_LIMIT = 100


def requested_fields(request) -> list[str]:
    raw = request.GET.get("fields", "")
    return [name.strip() for name in raw.split(",") if name.strip()]


def visible_tournaments(client):
    """Local drafts stay hidden; an upstream sees all of its own (11.5.1)."""
    from django.db.models import Q

    return Tournament.objects.filter(
        Q(source_client=client) | ~Q(status=TournamentStatus.DRAFT)
    ).select_related("cover", "source_client")


def split_values(request, name):
    raw = request.GET.get(name, "")
    return [value.strip() for value in raw.split(",") if value.strip()]


class TournamentListView(SignedApiView):
    required_scope = "tournaments:read"

    @extend_schema(
        operation_id="tournament_list",
        responses={200: OpenApiTypes.OBJECT},
    )
    def get(self, request):
        client = request.api_client
        queryset = visible_tournaments(client)
        statuses = split_values(request, "status")
        if statuses:
            queryset = queryset.filter(status__in=statuses)
        source = request.GET.get("source")
        if source == "local":
            queryset = queryset.filter(source_client__isnull=True)
        elif source == "upstream":
            queryset = queryset.filter(source_client__isnull=False)
        rows, next_cursor, has_more = paginate(queryset, request)
        payload = [tournament_data(row, client=client) for row in rows]
        return list_response(
            apply_fields(payload, requested_fields(request)),
            next_cursor=next_cursor,
            has_more=has_more,
        )


class TournamentDetailView(SignedApiView):
    required_scope = "tournaments:read"

    @extend_schema(
        operation_id="tournament_detail",
        responses={200: OpenApiTypes.OBJECT},
    )
    def get(self, request, pk):
        client = request.api_client
        tournament = visible_tournaments(client).filter(pk=pk).first()
        if tournament is None:
            raise ApiError("not_found", "赛事不存在")
        payload = tournament_data(tournament, client=client, with_description=True)
        return data_response(apply_fields(payload, requested_fields(request)))


class TournamentUpsertView(SignedApiView):
    """PUT by the upstream's own id: create or update (design 11.6.3)."""

    required_scope = "tournaments:write"
    REQUIRED = (
        "title",
        "registration_opens_at",
        "registration_closes_at",
        "roster_min",
        "roster_max",
        "review_mode",
    )

    @extend_schema(
        operation_id="tournament_upsert",
        request=OpenApiTypes.OBJECT,
        responses={200: OpenApiTypes.OBJECT, 201: OpenApiTypes.OBJECT},
    )
    def put(self, request, external_id):
        from tournaments import services as tournament_services

        client = request.api_client
        body = request.data if isinstance(request.data, dict) else {}
        missing = [name for name in self.REQUIRED if body.get(name) in (None, "")]
        if missing:
            raise ApiError(
                "validation_error",
                f"缺少必填字段：{'、'.join(missing)}",
                {"fields": missing},
            )

        tournament = Tournament.objects.filter(
            source_client=client, external_id=external_id
        ).first()
        created = tournament is None
        if created:
            tournament = Tournament(source_client=client, external_id=external_id)

        review_mode = body["review_mode"]
        if review_mode not in ReviewMode.values:
            raise ApiError("validation_error", "review_mode 不合法")
        if (
            not created
            and review_mode != tournament.review_mode
            and tournament_services.has_registrations(tournament)
        ):
            raise ApiError(
                "review_mode_locked",
                "已经有报名，不能修改审核模式",
                {"review_mode": tournament.review_mode},
            )

        opens_at = parse_datetime(str(body["registration_opens_at"]))
        closes_at = parse_datetime(str(body["registration_closes_at"]))
        if opens_at is None or closes_at is None:
            raise ApiError("validation_error", "报名时间必须是 ISO 8601 时间")
        if opens_at >= closes_at:
            raise ApiError("validation_error", "报名开始时间要早于截止时间")
        try:
            roster_min = int(body["roster_min"])
            roster_max = int(body["roster_max"])
        except (TypeError, ValueError) as exc:
            raise ApiError("validation_error", "参赛人数必须是整数") from exc
        if not (1 <= roster_min <= roster_max <= 20):
            raise ApiError("validation_error", "参赛人数需要满足 1 ≤ 下限 ≤ 上限 ≤ 20")

        status_value = body.get("status") or (
            tournament.status if not created else TournamentStatus.DRAFT
        )
        if status_value not in TournamentStatus.values:
            raise ApiError("validation_error", "status 不合法")

        tournament.title = str(body["title"])[:100]
        tournament.registration_opens_at = opens_at
        tournament.registration_closes_at = closes_at
        tournament.roster_min = roster_min
        tournament.roster_max = roster_max
        tournament.review_mode = review_mode
        tournament.status = status_value
        if "summary" in body:
            tournament.summary = str(body.get("summary") or "")[:300]
        if "description_html" in body:
            tournament.description = clean_html(str(body.get("description_html") or ""))
        if "starts_at" in body:
            tournament.starts_at = (
                parse_datetime(str(body["starts_at"])) if body["starts_at"] else None
            )
        if "sjtu_only" in body:
            tournament.sjtu_only = bool(body["sjtu_only"])
        first_publish = (
            status_value == TournamentStatus.PUBLISHED
            and tournament.published_at is None
        )
        if first_publish:
            tournament.published_at = timezone.now()
        tournament.save()
        tournament_services.after_change(tournament)

        payload = tournament_data(tournament, client=client, with_description=True)
        return data_response(payload, status_code=201 if created else 200)


def visible_registrations(client):
    return Registration.objects.select_related(
        "tournament", "team", "team__logo"
    ).prefetch_related("members", "logs")


class RegistrationListView(SignedApiView):
    required_scope = "registrations:read"

    @extend_schema(
        operation_id="registration_list",
        responses={200: OpenApiTypes.OBJECT},
    )
    def get(self, request):
        client = request.api_client
        includes = self.includes(request)
        queryset = visible_registrations(client)
        if request.GET.get("tournament"):
            queryset = queryset.filter(tournament_id=request.GET["tournament"])
        if request.GET.get("team"):
            queryset = queryset.filter(team_id=request.GET["team"])
        statuses = split_values(request, "status")
        if statuses:
            queryset = queryset.filter(status__in=statuses)
        rows, next_cursor, has_more = paginate(queryset, request)
        payload = [
            registration_data(row, includes=includes, client=client) for row in rows
        ]
        return list_response(
            apply_fields(payload, requested_fields(request)),
            next_cursor=next_cursor,
            has_more=has_more,
        )


class RegistrationDetailView(SignedApiView):
    required_scope = "registrations:read"

    @extend_schema(
        operation_id="registration_detail",
        responses={200: OpenApiTypes.OBJECT},
    )
    def get(self, request, pk):
        client = request.api_client
        includes = self.includes(request)
        registration = visible_registrations(client).filter(pk=pk).first()
        if registration is None:
            raise ApiError("not_found", "报名不存在")
        payload = registration_data(registration, includes=includes, client=client)
        return data_response(apply_fields(payload, requested_fields(request)))


class RegistrationLogsView(SignedApiView):
    required_scope = "registrations:read"

    @extend_schema(
        operation_id="registration_logs",
        responses={200: OpenApiTypes.OBJECT},
    )
    def get(self, request, pk):
        registration = Registration.objects.filter(pk=pk).first()
        if registration is None:
            raise ApiError("not_found", "报名不存在")
        return list_response(
            [log_data(entry) for entry in registration.logs.all()],
            next_cursor=None,
            has_more=False,
        )


# The status each action aims at, used for the idempotency check (11.6.7).
REVIEW_TARGETS = {
    "approve": RegistrationStatus.APPROVED,
    "reject": RegistrationStatus.REJECTED,
    "revoke": RegistrationStatus.REJECTED,
}


def perform_review(*, registration, client, action, roster_version, note):
    """One upstream decision, with the roster-version guard (design 11.6.7)."""
    from tournaments import registration as registration_service

    if action not in REVIEW_TARGETS:
        raise ApiError("validation_error", "action 只能是 approve / reject / revoke")
    if roster_version is None:
        raise ApiError("validation_error", "缺少 roster_version")
    try:
        sent_version = int(roster_version)
    except (TypeError, ValueError) as exc:
        raise ApiError("validation_error", "roster_version 必须是整数") from exc
    if sent_version != registration.roster_version:
        raise ApiError(
            "roster_version_mismatch",
            "名单已被队长更新，请重新获取后再审核",
            {"current_roster_version": registration.roster_version},
        )
    if not registration_service.upstream_review_allowed(registration.tournament):
        raise ApiError("review_not_allowed", "这项赛事由本站审核，上游不能改状态")
    if registration.status == REVIEW_TARGETS[action]:
        # Retrying after a network timeout must not write a second log entry
        # or send a second notification (design 11.6.7).
        return registration
    try:
        if action == "approve":
            registration_service.approve(
                registration=registration,
                actor=None,
                actor_type=ActorType.UPSTREAM,
            )
        else:
            registration_service.reject(
                registration=registration,
                actor=None,
                note=note or "",
                actor_type=ActorType.UPSTREAM,
            )
    except registration_service.RegistrationError as exc:
        raise _review_error(exc, registration) from exc
    registration.refresh_from_db()
    _stamp_client(registration, client)
    return registration


def _review_error(exc, registration):
    code = getattr(exc, "code", "invalid_state")
    if code == "review_not_allowed":
        return ApiError("review_not_allowed", str(exc))
    if code == "validation_error":
        return ApiError("validation_error", str(exc))
    return ApiError(
        "invalid_state_transition",
        str(exc),
        {"current_status": registration.status},
    )


def _stamp_client(registration, client):
    """Design 12.8.4: upstream actions record which client acted."""
    entry = registration.logs.order_by("-created_at", "-id").first()
    if entry is not None and entry.actor_type == ActorType.UPSTREAM:
        entry.actor_client = client
        entry.save(update_fields=["actor_client"])


class RegistrationReviewView(SignedApiView):
    required_scope = "registrations:review"

    @extend_schema(
        operation_id="registration_review",
        request=OpenApiTypes.OBJECT,
        responses={200: OpenApiTypes.OBJECT},
    )
    def post(self, request, pk):
        client = request.api_client
        registration = Registration.objects.filter(pk=pk).first()
        if registration is None:
            raise ApiError("not_found", "报名不存在")
        body = request.data if isinstance(request.data, dict) else {}
        registration = perform_review(
            registration=registration,
            client=client,
            action=body.get("action"),
            roster_version=body.get("roster_version"),
            note=body.get("note"),
        )
        return data_response(registration_data(registration, client=client))


class RegistrationReviewBatchView(SignedApiView):
    required_scope = "registrations:review"

    @extend_schema(
        operation_id="registration_review_batch",
        request=OpenApiTypes.OBJECT,
        responses={200: OpenApiTypes.OBJECT},
    )
    def post(self, request):
        client = request.api_client
        body = request.data if isinstance(request.data, dict) else {}
        items = body.get("items") or []
        if not isinstance(items, list):
            raise ApiError("validation_error", "items 必须是数组")
        if len(items) > BATCH_LIMIT:
            raise ApiError(
                "validation_error", f"一次最多 {BATCH_LIMIT} 条", {"limit": BATCH_LIMIT}
            )
        results = []
        for item in items:
            pk = item.get("id")
            registration = Registration.objects.filter(pk=pk).first()
            if registration is None:
                results.append(
                    {
                        "id": pk,
                        "ok": False,
                        "error": {"code": "not_found", "message": "报名不存在"},
                    }
                )
                continue
            try:
                with transaction.atomic():
                    registration = perform_review(
                        registration=registration,
                        client=client,
                        action=item.get("action"),
                        roster_version=item.get("roster_version"),
                        note=item.get("note"),
                    )
            except ApiError as exc:
                entry = {
                    "id": pk,
                    "ok": False,
                    "error": {"code": exc.code, "message": exc.message},
                }
                if exc.details:
                    entry["error"]["details"] = exc.details
                results.append(entry)
            else:
                results.append(
                    {
                        "id": pk,
                        "ok": True,
                        "registration": {
                            "id": registration.pk,
                            "status": registration.status,
                        },
                    }
                )
        return data_response(results)


def roster_registrations(tournament, request):
    statuses = split_values(request, "status") or [RegistrationStatus.APPROVED]
    return (
        tournament.registrations.filter(status__in=statuses)
        .select_related("team", "team__logo")
        .prefetch_related("members")
        .order_by("submitted_at", "id")
    )


class TournamentRosterView(SignedApiView):
    required_scope = "registrations:read"

    @extend_schema(
        operation_id="tournament_roster",
        responses={200: OpenApiTypes.OBJECT},
    )
    def get(self, request, pk):
        client = request.api_client
        includes = self.includes(request)
        tournament = visible_tournaments(client).filter(pk=pk).first()
        if tournament is None:
            raise ApiError("not_found", "赛事不存在")
        with_ranks = "members.ranks" in includes
        registrations = []
        for registration in roster_registrations(tournament, request):
            registrations.append(
                {
                    "id": registration.pk,
                    "status": registration.status,
                    "roster_version": registration.roster_version,
                    "team": team_data(registration.team),
                    "members": [
                        member_data(member, with_ranks=with_ranks)
                        for member in registration.members.all()
                    ],
                }
            )
        return data_response(
            {
                "tournament": {
                    "id": tournament.pk,
                    "title": tournament.title,
                    "status": tournament.status,
                },
                "registrations": registrations,
            }
        )


class TournamentRosterCsvView(SignedApiView):
    required_scope = "registrations:read"

    @extend_schema(
        operation_id="tournament_roster_csv",
        responses={200: OpenApiTypes.STR},
    )
    def get(self, request, pk):
        from accounts.ranks import format_rank

        client = request.api_client
        includes = self.includes(request)
        tournament = visible_tournaments(client).filter(pk=pk).first()
        if tournament is None:
            raise ApiError("not_found", "赛事不存在")
        with_ranks = "members.ranks" in includes

        response = HttpResponse(content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = (
            f'attachment; filename="tournament-{tournament.pk}-roster.csv"'
        )
        response.write("﻿")
        writer = csv.writer(response)
        header = [
            "registration_id",
            "status",
            "roster_version",
            "team_id",
            "team_name",
            "user_id",
            "nickname",
            "battletag",
            "is_sjtu",
            "is_captain",
        ]
        if with_ranks:
            header += ["rank_tank", "rank_damage", "rank_support"]
        writer.writerow(header)
        for registration in roster_registrations(tournament, request):
            for member in registration.members.all():
                row = [
                    registration.pk,
                    registration.status,
                    registration.roster_version,
                    registration.team_id,
                    registration.team_name,
                    member.user_id,
                    member.nickname,
                    member.battletag,
                    "true" if member.is_sjtu else "false",
                    "true" if member.is_captain else "false",
                ]
                if with_ranks:
                    row += [
                        format_rank(member.rank_tank),
                        format_rank(member.rank_damage),
                        format_rank(member.rank_support),
                    ]
                writer.writerow(row)
        return response


class TournamentStatsView(SignedApiView):
    required_scope = "registrations:read"

    @extend_schema(
        operation_id="tournament_stats",
        responses={200: OpenApiTypes.OBJECT},
    )
    def get(self, request, pk):
        from django.db.models import Count

        client = request.api_client
        tournament = visible_tournaments(client).filter(pk=pk).first()
        if tournament is None:
            raise ApiError("not_found", "赛事不存在")
        counts = {status: 0 for status in RegistrationStatus.values}
        rows = tournament.registrations.values("status").annotate(total=Count("id"))
        for row in rows:
            counts[row["status"]] = row["total"]
        active = tournament.roster_members.filter(
            is_active=True, registration__status__in=ACTIVE_STATUSES
        )
        sjtu = active.filter(is_sjtu=True).count()
        total = active.count()
        latest = (
            tournament.registrations.order_by("-updated_at")
            .values_list("updated_at", flat=True)
            .first()
        )
        return data_response(
            {
                "tournament_id": tournament.pk,
                "registrations_by_status": counts,
                "active_members": total,
                "active_sjtu_members": sjtu,
                "active_non_sjtu_members": total - sjtu,
                "updated_at": isoformat(latest or tournament.updated_at),
            }
        )

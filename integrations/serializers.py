"""API object shapes (design 11.5). Contact details never appear here."""

from __future__ import annotations

from integrations.api import ApiError, isoformat

TOURNAMENT_FIELDS = (
    "id",
    "source",
    "external_id",
    "title",
    "summary",
    "cover_url",
    "status",
    "starts_at",
    "registration_opens_at",
    "registration_closes_at",
    "roster_min",
    "roster_max",
    "sjtu_only",
    "review_mode",
    "url",
    "created_at",
    "updated_at",
)
REGISTRATION_FIELDS = (
    "id",
    "tournament_id",
    "team_id",
    "team_name",
    "status",
    "roster_version",
    "member_count",
    "status_note",
    "submitted_at",
    "created_at",
    "updated_at",
)
TEAM_FIELDS = ("id", "name", "logo_url", "url", "disbanded")
MEMBER_FIELDS = ("user_id", "nickname", "battletag", "is_sjtu", "is_captain")
LOG_FIELDS = (
    "id",
    "from_status",
    "to_status",
    "action",
    "actor_type",
    "roster_version",
    "note",
    "created_at",
)
INCLUDE_KEYS = {"tournament", "team", "members", "logs"}


def absolute(path: str) -> str:
    from django.conf import settings

    base = (getattr(settings, "SITE_URL", "") or "").rstrip("/")
    return f"{base}{path}" if path else ""


def image_url(image) -> str | None:
    if image is None:
        return None
    try:
        rendition = image.get_rendition("fill-200x200")
    except Exception:  # noqa: BLE001 — a broken file must not break the API
        return None
    return absolute(rendition.url)


def tournament_data(tournament, *, client=None, with_description=False) -> dict:
    mine = (
        client is not None
        and tournament.source_client_id is not None
        and tournament.source_client_id == client.pk
    )
    data = {
        "id": tournament.pk,
        "source": "upstream" if tournament.source_client_id else "local",
        # Only the upstream that pushed it may see its own external id.
        "external_id": tournament.external_id if mine else None,
        "title": tournament.title,
        "summary": tournament.summary,
        "cover_url": image_url(tournament.cover),
        "status": tournament.status,
        "starts_at": isoformat(tournament.starts_at),
        "registration_opens_at": isoformat(tournament.registration_opens_at),
        "registration_closes_at": isoformat(tournament.registration_closes_at),
        "roster_min": tournament.roster_min,
        "roster_max": tournament.roster_max,
        "sjtu_only": tournament.sjtu_only,
        "review_mode": tournament.review_mode,
        "url": absolute(tournament.get_absolute_url()),
        "created_at": isoformat(tournament.created_at),
        "updated_at": isoformat(tournament.updated_at),
    }
    if with_description:
        data["description_html"] = tournament.description or ""
    return data


def team_data(team) -> dict:
    return {
        "id": team.pk,
        "name": team.name,
        "logo_url": image_url(team.logo),
        "url": absolute(team.get_absolute_url()),
        "disbanded": team.is_disbanded,
    }


def rank_data(score) -> dict | None:
    from accounts.ranks import decode_rank, format_rank

    if score is None:
        return None
    tier, division = decode_rank(score)
    return {
        "score": score,
        "tier": tier,
        "division": division,
        "label": format_rank(score),
    }


def member_data(member, *, with_ranks=False) -> dict:
    data = {
        "user_id": member.user_id,
        "nickname": member.nickname,
        "battletag": member.battletag,
        "is_sjtu": member.is_sjtu,
        "is_captain": member.is_captain,
    }
    if with_ranks:
        data["ranks"] = {
            "tank": rank_data(member.rank_tank),
            "damage": rank_data(member.rank_damage),
            "support": rank_data(member.rank_support),
        }
    return data


def log_data(entry) -> dict:
    """No actor identity: upstreams never learn which admin acted (11.5)."""
    return {
        "id": entry.pk,
        "from_status": entry.from_status or None,
        "to_status": entry.to_status,
        "action": entry.action,
        "actor_type": entry.actor_type,
        "roster_version": entry.roster_version,
        "note": entry.note,
        "created_at": isoformat(entry.created_at),
    }


def registration_data(registration, *, includes=(), client=None) -> dict:
    data = {
        "id": registration.pk,
        "tournament_id": registration.tournament_id,
        "team_id": registration.team_id,
        "team_name": registration.team_name,
        "status": registration.status,
        "roster_version": registration.roster_version,
        "member_count": registration.members.count(),
        "status_note": registration.status_note,
        "submitted_at": isoformat(registration.submitted_at),
        "created_at": isoformat(registration.created_at),
        "updated_at": isoformat(registration.updated_at),
    }
    if "tournament" in includes:
        data["tournament"] = tournament_data(registration.tournament, client=client)
    if "team" in includes:
        data["team"] = team_data(registration.team)
    if "members" in includes:
        with_ranks = "members.ranks" in includes
        data["members"] = [
            member_data(member, with_ranks=with_ranks)
            for member in registration.members.all()
        ]
    if "logs" in includes:
        data["logs"] = [log_data(entry) for entry in registration.logs.all()]
    return data


def _known_fields(sample) -> set[str]:
    known = set()
    for key, value in sample.items():
        known.add(key)
        if isinstance(value, dict):
            known.update(f"{key}.{inner}" for inner in value)
        elif isinstance(value, list) and value and isinstance(value[0], dict):
            known.update(f"{key}.{inner}" for inner in value[0])
    return known


def apply_fields(payload, requested):
    """``fields`` filtering with dotted paths; ``id`` always stays (11.4)."""
    if not requested:
        return payload
    if isinstance(payload, list):
        return [apply_fields(item, requested) for item in payload]

    known = _known_fields(payload)
    for name in requested:
        if name not in known:
            raise ApiError("invalid_field", f"没有字段「{name}」", {"field": name})

    top = {name.split(".")[0] for name in requested}
    nested: dict[str, set[str]] = {}
    for name in requested:
        if "." in name:
            parent, child = name.split(".", 1)
            nested.setdefault(parent, set()).add(child)

    result = {}
    for key, value in payload.items():
        if key == "id" or key in top:
            children = nested.get(key)
            if children and isinstance(value, dict):
                result[key] = {
                    inner: sub
                    for inner, sub in value.items()
                    if inner in children or inner in ("id", "user_id")
                }
            elif children and isinstance(value, list):
                result[key] = [
                    {
                        inner: sub
                        for inner, sub in item.items()
                        if inner in children or inner in ("id", "user_id")
                    }
                    for item in value
                ]
            else:
                result[key] = value
    return result

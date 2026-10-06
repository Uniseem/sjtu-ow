"""Autosave (design 13.17, v7.6): the server's half.

``static/js/autosave.js`` posts a form with ``data-autosave`` to the address
it would submit to, adding the header ``X-Autosave: 1``; the same view saves
what it can and answers with JSON instead of a redirect. Without the script
the form submits as it always did.

The rule: a valid form is saved whole. Otherwise every changed field that is
valid on its own is saved and every field with an error keeps its stored
value, the page saying why; when a rule across fields fails, the fields the
form names in ``autosave_together`` are not saved this time either — whether
the rule reported itself on the form (``__all__``) or on one field of the
group (v7.10 does that, so the note sits under a field). If the form names
no group for a form-level error, nothing is.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta

from django.core.exceptions import NON_FIELD_ERRORS
from django.db import IntegrityError, transaction
from django.http import JsonResponse
from django.utils import timezone

HEADER = "X-Autosave"
# The same person's edits to the same thing merge into one log entry.
LOG_MERGE = timedelta(minutes=30)


def wants(request) -> bool:
    return request.method == "POST" and request.headers.get(HEADER) == "1"


@dataclass
class Outcome:
    saved: list = field(default_factory=list)
    errors: dict = field(default_factory=dict)
    location: str = ""  # the edit address once something new exists
    replace: dict = field(default_factory=dict)  # CSS selector -> new HTML
    # Field name -> the value the server gave it (an article's address that
    # follows its title, v7.9); the page shows it so the next save agrees.
    values: dict = field(default_factory=dict)


def errors_of(form) -> dict[str, list[str]]:
    """Keyed by the field's name in the page (prefix included); the form's
    own errors under ``__all__``."""
    found: dict[str, list[str]] = {}
    for name, errors in form.errors.items():
        key = NON_FIELD_ERRORS if name == NON_FIELD_ERRORS else form.add_prefix(name)
        found[key] = [str(error) for error in errors]
    return found


def respond(outcome: Outcome) -> JsonResponse:
    return JsonResponse(
        {
            "ok": not outcome.errors,
            "saved": outcome.saved,
            "errors": outcome.errors,
            "location": outcome.location,
            "replace": outcome.replace,
            "values": outcome.values,
            "saved_at": timezone.localtime().strftime("%H:%M"),
        }
    )


def _together_groups(form) -> list[set[str]]:
    """``autosave_together`` as a list of groups: a bare field name is a
    one-field group, a tuple is a rule that spans those fields (212: the
    roster range and the registration window are two rules, not one)."""
    groups = []
    for item in getattr(form, "autosave_together", None) or ():
        groups.append({item} if isinstance(item, str) else set(item))
    return groups


def valid_changes(form) -> list[str]:
    """The changed fields that may be saved now (the rule above)."""
    if form.is_valid():
        return list(form.changed_data)
    bad = set(form.errors) - {NON_FIELD_ERRORS}
    groups = _together_groups(form)
    if NON_FIELD_ERRORS in form.errors:
        # The form's own error names no field: without a registered group
        # nothing may be saved; with one, the group sits this save out.
        if not groups:
            return []
        for group in groups:
            bad |= group
    else:
        for group in groups:
            if bad & group:
                # A rule across fields reported on one field of the group
                # (212): saving another field of the group alone would break
                # the pair, so the whole group sits this save out too.
                bad |= group
    return [
        name
        for name in form.changed_data
        if name not in bad and name in form.cleaned_data
    ]


def save_valid_fields(form) -> list[str]:
    """Save a bound ModelForm by the rule: whole when valid (its own save()
    runs), else only the changed fields that are fine, written to a fresh
    copy of the stored row. Returns the field names saved; fields that are
    not model fields are left to the view (it knows what they mean)."""
    if form.is_valid():
        names = list(form.changed_data)
        form.save()
        return names
    names = valid_changes(form)
    instance = form.instance
    if not names or instance.pk is None:
        return []
    model = instance._meta.model  # request.user comes wrapped
    stored = model._default_manager.get(pk=instance.pk)
    concrete, many = _apply(form, stored, names)
    try:
        with transaction.atomic():
            if concrete:
                stored.save(update_fields=concrete)
            for name, value in many:
                getattr(stored, name).set(value)
    except IntegrityError:
        return []
    form.instance = stored
    return [name for name, _ in many] + concrete


def _apply(form, target, names):
    """Write the named fields' cleaned values onto ``target``; returns the
    plain fields written and the many-to-many ones left to set after."""
    model = target._meta.model
    concrete, many = [], []
    for name in names:
        try:
            model_field = model._meta.get_field(name)
        except Exception:  # noqa: BLE001 - a form-only field
            continue
        value = form.cleaned_data[name]
        if model_field.many_to_many:
            many.append((name, value))
        else:
            model_field.save_form_data(target, value)
            concrete.append(name)
    return concrete, many


def new_from_valid_fields(form, fresh):
    """Something new from its first change (v7.6, v7.10), required fields
    empty or not: the whole form when it is valid, otherwise ``fresh`` (an
    unsaved instance as it stood before the form touched it, a copy's
    fields already in it) with the changed fields that are fine. Returns
    (unsaved instance, field names); the caller saves it."""
    if form.is_valid():
        return form.save(commit=False), list(form.changed_data)
    names = valid_changes(form)
    concrete, _many = _apply(form, fresh, names)
    return fresh, concrete


def log_edit(instance, user, action: str = "wagtail.edit", **data) -> None:
    """One log entry per stretch of editing (13.17): the same person's
    edits to the same thing within LOG_MERGE move the last entry's time
    forward instead of adding one per autosave."""
    from wagtail.log_actions import log
    from wagtail.log_actions import registry as log_registry

    model = log_registry.get_log_model_for_instance(instance)
    recent = (
        model.objects.for_instance(instance)
        .filter(action=action, user=user, timestamp__gte=timezone.now() - LOG_MERGE)
        .order_by("-timestamp")
        .first()
        if user is not None and getattr(user, "pk", None)
        else None
    )
    if recent is not None:
        model.objects.filter(pk=recent.pk).update(timestamp=timezone.now())
        return
    extra = {"data": data} if data else {}
    # An entry needs a label; a draft may not have a name yet (v7.10).
    log(instance, action, user=user, title=str(instance) or "（未命名）", **extra)

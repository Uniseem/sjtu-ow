# Seed an "old" (round 066) database with everything round 067 has to migrate.
# Run inside the 066 worktree: python manage.py shell < drill_seed_066.py
from datetime import timedelta

from django.utils import timezone

from accounts.models import ContactMethod, ContactType, GameAccount, User
from integrations import services as api_services
from integrations.tasks import deliver_due_webhooks
from teams import services as team_services
from tournaments import registration as reg
from tournaments.models import (
    Registration,
    RegistrationStatus,
    ReviewMode,
    Tournament,
    TournamentStatus,
)

now = timezone.now()


def player(email, nick):
    user = User.objects.create_user(
        email=email,
        password="Correct-Horse-Battery-1",
        nickname=nick,
        is_sjtu=True,
        agreed_terms_at=now,
        agreed_cross_border_at=now,
    )
    GameAccount.objects.create(user=user, battletag=f"{nick}#7000", rank_damage=20)
    ContactMethod.objects.create(user=user, type=ContactType.QQ, value="123456789")
    return user


client, _secret = api_services.create_client(
    name="演练上游", scopes=["tournaments:read", "registrations:review"], allowed_includes=[]
)
tournament = Tournament.objects.create(
    title="演练两级审核赛事",
    registration_opens_at=now - timedelta(days=1),
    registration_closes_at=now + timedelta(days=7),
    roster_min=2,
    roster_max=3,
    status=TournamentStatus.PUBLISHED,
    published_at=now,
    review_mode=ReviewMode.TWO_STAGE,
    source_client=client,
    external_id="up-1",
)
Tournament.objects.create(
    title="演练本站审核赛事",
    registration_opens_at=now - timedelta(days=1),
    registration_closes_at=now + timedelta(days=7),
    roster_min=2,
    roster_max=3,
    status=TournamentStatus.PUBLISHED,
    published_at=now,
    review_mode=ReviewMode.LOCAL,
)
captain = player("drill-cap@example.com", "演练队长")
mate = player("drill-mate@example.com", "演练队员")
team = team_services.create_team(user=captain, name="演练战队")
application = team_services.apply_to_team(team=team, user=mate, roles={"tank": True})
team_services.approve_application(application=application, actor=captain)
selections = {
    str(m.user.pk): m.user.game_accounts.first().pk for m in team.memberships.all()
}
registration = reg.submit(
    tournament=tournament, team=team, actor=captain, selections=selections
)
Registration.objects.filter(pk=registration.pk).update(
    status=RegistrationStatus.AWAITING_UPSTREAM
)
deliver_due_webhooks.enqueue()

from django_tasks_db.models import DBTaskResult  # noqa: E402

print(
    "seeded:",
    "registration status =", Registration.objects.get(pk=registration.pk).status,
    "| integrations tasks =",
    DBTaskResult.objects.filter(task_path__startswith="integrations.").count(),
    "| other tasks =",
    DBTaskResult.objects.exclude(task_path__startswith="integrations.").count(),
    "| api clients =", api_services.ApiClient.objects.count()
    if hasattr(api_services, "ApiClient") else "n/a",
)

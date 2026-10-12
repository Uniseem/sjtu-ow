"""Addresses and applicable identities, shared by visual parity and real journeys.

No generated page may disappear because a role has no capabilities: its login,
403 or 404 result is part of the matrix. Account verification contexts remain
in account_scenarios, rather than pretending they are ordinary GET pages.
"""
from account_scenarios import ROLES

FRONT = (
    ('home', '/'), ('news', '/news/'), ('article', '/news/screens-guide/'),
    ('about', '/about/'), ('terms', '/terms/'), ('privacy', '/privacy/'),
    ('search', '/search/?q=截图'), ('submit', '/submit/'),
    ('teams', '/teams/'), ('team', '/teams/{team}/'),
    ('team-new', '/teams/new/'), ('team-apply', '/teams/{team}/apply/'),
    ('team-manage', '/teams/{team}/manage/'), ('members', '/members/'),
    ('members-filter', '/members/?role=support&free=1'), ('member', '/members/{member}/'),
    ('tournaments', '/tournaments/'), ('cup', '/tournaments/{cup}/'),
    ('teamcup', '/tournaments/{teamcup}/'), ('cup-signup', '/tournaments/{cup}/signup/'),
    ('teamcup-register', '/tournaments/{teamcup}/register/'),
    ('registration', '/registrations/{registration}/'), ('scrims', '/scrims/'),
    ('scrim', '/scrims/{scrim}/'), ('me', '/me/'),
    ('me-game-accounts', '/me/game-accounts/'), ('me-game-account', '/me/game-accounts/{game_account}/'),
    ('me-contacts', '/me/contacts/'), ('me-contact', '/me/contacts/{contact}/'),
    ('me-security', '/me/security/'), ('me-delete', '/me/delete/'),
    ('me-teams', '/me/teams/'), ('me-registrations', '/me/registrations/'),
    ('me-scrims', '/me/scrims/'), ('letters', '/letters/'),
    ('letters-confirm', '/letters/{front_letters}/'),
    ('letter-preview', '/letters/{front_letters}/{front_letter}/'),
    ('styleguide', '/_styleguide/'),
    ('email-samples', '/_styleguide/emails/'),
    ('email-sample', '/_styleguide/emails/verify/'),
    ('unsubscribe-valid', '/unsubscribe/{unsubscribe}/'),
    ('unsubscribe-done', '/unsubscribe/{unsubscribe_done}/'),
    ('unsubscribe-invalid', '/unsubscribe/invalid/'),
)

# The old server is the authority for the physical URLs, including edit/id order.
ADMIN = (
    ('admin-home', '/admin/'), ('admin-letters', '/admin/letters/'),
    ('admin-letters-confirm', '/admin/letters/{back_letters}/'),
    ('admin-letter-preview', '/admin/letters/{back_letters}/{back_letter}/'),
    ('admin-articles', '/admin/articles/'), ('admin-article-new', '/admin/articles/new/'),
    ('admin-article', '/admin/articles/{article}/'),
    ('admin-article-preview', '/admin/articles/{article}/preview/'),
    ('admin-article-revisions', '/admin/articles/{article}/revisions/'),
    ('admin-article-revision', '/admin/articles/{article}/revisions/{revision}/'),
    ('admin-categories', '/admin/categories/'), ('admin-category-new', '/admin/categories/new/'),
    ('admin-category', '/admin/categories/{category}/'), ('admin-pages', '/admin/pages/'),
    ('admin-pins', '/admin/pages/pins/'), ('admin-intro', '/admin/pages/intro/'),
    ('admin-page', '/admin/pages/{about}/'), ('admin-images', '/admin/images/'),
    ('admin-upload', '/admin/images/upload/'), ('admin-image', '/admin/images/{image}/'),
    ('admin-collections', '/admin/images/collections/'),
    ('admin-users', '/admin/users/'), ('admin-user', '/admin/users/{member}/'),
    ('admin-roles', '/admin/roles/'), ('admin-teams', '/admin/teams/'),
    ('admin-team', '/admin/teams/edit/{team}/'),
    ('admin-team-assign-captain', '/admin/teams/{team}/assign-captain/'),
    ('admin-team-disband', '/admin/teams/{team}/disband/'), ('admin-groups', '/admin/member-groups/'),
    ('admin-group-new', '/admin/member-groups/new/'), ('admin-group', '/admin/member-groups/{group}/'),
    ('admin-registrations', '/admin/registrations/'),
    ('admin-registration', '/admin/registrations/{registration}/'),
    ('admin-comments', '/admin/comments/'), ('admin-avatars', '/admin/avatars/'),
    ('admin-moderation', '/admin/moderation/'), ('admin-activity', '/admin/activity/'),
    ('admin-settings', '/admin/settings/site/'), ('admin-fonts', '/admin/settings/fonts/'),
    ('admin-font-add', '/admin/settings/fonts/add/'),
    ('admin-font-detail', '/admin/settings/fonts/{font}/'),
    ('admin-font-delete', '/admin/settings/fonts/{font}/delete/'),
    ('admin-font-download', '/admin/settings/fonts/weights/{font_face}/download/'),
    ('admin-moderation-detail', '/admin/moderation/{moderation}/'),
    ('admin-moderation-motto', '/admin/moderation/{moderation_motto}/'),
    ('admin-typography', '/admin/settings/typography/'), ('admin-log', '/admin/log/'),
    ('admin-manual', '/admin/manual/'), ('admin-mail-samples', '/admin/settings/email-samples/'),
    ('admin-mail-sample', '/admin/settings/email-samples/verify/'),
    ('admin-prerender-redirect', '/admin/settings/prerender/'),
    ('admin-team-board', '/admin/tournaments/{teamcup}/teams/'),
    ('admin-split-board', '/admin/scrims/{scrim}/split/'),
    ('admin-split-text', '/admin/scrims/{scrim}/split/text/'),
    ('admin-tournament-announce', '/admin/announce/tournament/{cup}/'),
    ('admin-tournament-announce-participants', '/admin/announce/tournament/{cup}/?to=participants'),
    ('admin-scrim-announce', '/admin/announce/scrim/{scrim}/'),
    ('admin-scrim-announce-participants', '/admin/announce/scrim/{scrim}/?to=participants'),
)
for kind, key in (('tournaments', 'cup'), ('scrims', 'scrim')):
    placeholder = '{' + key + '}'
    ADMIN += (
        (f'admin-{kind}', f'/admin/{kind}/'),
        (f'admin-{kind}-new', f'/admin/{kind}/new/'),
        (f'admin-{kind}-edit', f'/admin/{kind}/edit/{placeholder}/'),
        (f'admin-{kind}-copy', f'/admin/{kind}/copy/{placeholder}/'),
        (f'admin-{kind}-delete', f'/admin/{kind}/delete/{placeholder}/'),
        (f'admin-{kind}-cancel', f'/admin/{kind}/{placeholder}/cancel/'),
    )
    for action in ('publish', 'finish'):
        suffix = 'action/' + action if kind == 'tournaments' else action
        action_placeholder = '{' + key + '_draft}' if action == 'publish' else placeholder
        ADMIN += ((f'admin-{kind}-{action}', f'/admin/{kind}/{action_placeholder}/{suffix}/'),)

RESOURCES = (
    ('sitemap', '/sitemap.xml'), ('robots', '/robots.txt'),
    ('favicon', '/favicon.ico'), ('apple-touch-icon', '/apple-touch-icon.png'),
)

# 295 user-approved additions: equivalent legacy gate, no legacy visual page.
APPROVED_ADDITIONS = {
    'admin-article-revisions': ('文章修订', '/admin/articles/{article}/'),
    'admin-article-revision': ('查看修订', '/admin/articles/{article}/'),
    'admin-mail-samples': ('邮件样张', '/admin/letters/'),
    'admin-mail-sample': ('注册 / 修改邮箱验证码', '/admin/letters/'),
}


def expand(addresses, roles=ROLES):
    result = [(name, role, path) for name, path in addresses for role in roles]
    if len(set(result)) != len(result):
        raise ValueError('duplicate page/role in matrix')
    return result


def admin_roles(name):
    """Distinct gate states required by final-batch §3.2b.

    Keep all seven where owner data, writer fields or role-specific content
    differ. Do not screenshot the same forbidden document for every cadre.
    The Go capability matrix still covers every role on every API.
    """
    if name.startswith(('admin-tournaments', 'admin-tournament-announce')) or name in ('admin-team-board', 'admin-registrations', 'admin-registration'):
        return ('visitor', 'scrim_admin', 'tournament_admin', 'officer')
    if name.startswith(('admin-scrims', 'admin-scrim-announce', 'admin-split')):
        return ('visitor', 'tournament_admin', 'scrim_admin', 'officer')
    if name.startswith(('admin-categor', 'admin-page', 'admin-group', 'admin-moderation')) or name in ('admin-pins', 'admin-intro', 'admin-comments', 'admin-avatars'):
        return ('visitor', 'tournament_admin', 'content_editor', 'officer')
    if name.startswith(('admin-font', 'admin-user', 'admin-role', 'admin-team-', 'admin-collection')) or name in ('admin-settings', 'admin-typography', 'admin-log', 'admin-prerender-redirect', 'admin-teams'):
        return ('visitor', 'content_editor', 'officer')
    if name == 'admin-activity':
        return ('visitor', 'member', 'tournament_admin', 'officer')
    return ROLES


PAGES = expand(FRONT) + [row for name, path in ADMIN for row in expand(((name, path),), admin_roles(name))] + expand(RESOURCES, ('visitor',))


def negative_probe(compare):
    baseline = dict(title='page', text=['real'], links=[], fields=[], broken=[])
    damaged = {**baseline, 'text': ['wrong']}
    if not compare(baseline, damaged, 0, (200, 200)):
        raise RuntimeError('matrix comparator missed changed content')
    if not compare(baseline, baseline, 0.01, (200, 200)):
        raise RuntimeError('matrix comparator missed screenshot threshold')
    if not compare(baseline, baseline, 0, (403, 200)):
        raise RuntimeError('matrix comparator missed permission status')

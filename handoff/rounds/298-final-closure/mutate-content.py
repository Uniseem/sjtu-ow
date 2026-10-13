"""Compile-preserving mutations for the 298 content lifecycle regressions."""
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[3]
PACKAGE = './internal/content'
CASES = [
    ('category live and approved references', 'server/internal/content/store.go', [
        (re.escape('if count := usage.References[id]; count > 0 {'),
         'if count := usage.Counts[id]; count > 0 {'),
        (re.escape('"SELECT COUNT(*) FROM articles WHERE category_id=?"'),
         '"SELECT COUNT(*) FROM articles WHERE category_id=? AND 0"'),
    ], 'TestCategoryUsageAndDeletionIncludeLatestArticleDraft|TestSchedulingRevisionKeepsPublishedArticleAndLaterDraftSeparate'),
    ('worker publishes approved B rather than private C', 'server/internal/content/scheduled_articles.go', [
        (re.escape('readArticleRevisionContent(content, articleDraft(article))'),
         'readArticleRevisionContent(func() string { var latest string; if article.LatestRevisionID != nil { _ = tx.QueryRowContext(ctx, "SELECT content FROM page_revisions WHERE id=?", *article.LatestRevisionID).Scan(&latest) }; return latest }(), articleDraft(article))'),
    ], 'TestScheduledWorkerPublishesApprovedRevisionAndKeepsNewerPrivateDraft'),
    ('worker expires live article and cancels approval', 'server/internal/content/scheduled_articles.go', [
        (r'(func expiryCandidates\b[\s\S]*?if at\.Before\(now\))(\s*\{)', r'\1 && false\2'),
    ], 'TestScheduledWorkerExpiryCancelsPlansAndCannotResurrectWithdrawnArticle'),
    ('import keeps missing builtin under legacy root', 'server/internal/content/import.go', [
        (re.escape('UPDATE image_collections SET parent_id=? WHERE key=? AND parent_id IS NULL AND id<>?'),
         'UPDATE image_collections SET parent_id=? WHERE key=? AND parent_id IS NULL AND id<>? AND 0'),
    ], 'TestImportContentParentLinks'),
    ('import retains existing root selection key', 'server/internal/content/import.go', [
        (re.escape('THEN image_collections.key ELSE excluded.key END'),
         'THEN excluded.key ELSE excluded.key END'),
    ], 'TestImportContentParentLinks'),
    ('cleared author falls back to owner', 'server/internal/content/service.go', [
        (r'revContent\.AuthorID = &owner(\s*retValues\["author_id"\])', r'revContent.AuthorID = nil\1'),
    ], 'TestClearingArticleAuthorFallsBackToOwnerRatherThanEditingUser'),
]

for index, (name, file, changes, test) in enumerate(CASES):
    path = ROOT / file
    original = path.read_text(encoding='utf-8')
    damaged = original
    for pattern, replacement in changes:
        damaged, count = re.subn(pattern, replacement, damaged)
        if count != 1:
            raise RuntimeError(f'nonunique mutation {name}: {count}')
    log = ROOT.parent / f'298-content-mutation-{index}.log'
    try:
        path.write_text(damaged, encoding='utf-8')
        with log.open('w', encoding='utf-8') as output:
            result = subprocess.run(
                ['go', 'test', PACKAGE, '-run', test, '-count=1'],
                cwd=ROOT / 'server', stdout=output, stderr=subprocess.STDOUT,
                timeout=240,
            )
        evidence = log.read_text(encoding='utf-8')
        if result.returncode == 0 or '--- FAIL:' not in evidence or 'build failed' in evidence:
            raise RuntimeError('mutation did not fail assertions: ' + name + '\n' + evidence[-2000:])
        print('CONTENT-MUTATION-CAUGHT ' + name, flush=True)
    finally:
        path.write_text(original, encoding='utf-8')
print('CONTENT-MUTATIONS-298-OK ' + str(len(CASES)), flush=True)

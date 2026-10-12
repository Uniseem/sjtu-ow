"""Assertion-level probes for the confirmed294 defects; restore every file."""
from pathlib import Path
import re
import subprocess
ROOT=Path(__file__).resolve().parents[3]
CASES=[
 ('activity export cap','server/internal/activity/api.go',re.escape('if !viewer.HasCap(accounts.CapActivityView) {\n\t\thttp.Error'), 'if false {\n\t\thttp.Error', './internal/activity','TestCSVExportRequiresActivityCapability'),
 ('multipart anonymous gate','server/internal/platform/media/api.go',r'if viewer == nil \|\| viewer.Disabled', 'if false', './internal/platform/media','TestRound294MultipartUploadRejectsMissingSession'),
 ('contributor cover selection','server/internal/platform/media/permissions.go',re.escape('query += " AND collection_id IN (" + contributedCollections + ")"'),'query += ""','./internal/content','TestRound294ContributorCannotChooseOtherLibrary'),
 ('zip64 budget','server/internal/fonts/package.go',r'if file.UncompressedSize64 > uint64\(MaxPackageBytes\)-total', 'if false', './internal/fonts','TestPackageZip64SizeCannotOverflow'),
 ('current avatar protection','server/internal/accounts/avatar_review.go',r'image.Int64 != current.Int64','false','./internal/accounts','TestAvatarReviewCannotRetireReplacedUpload'),
 ('retired avatar metadata','server/internal/accounts/avatar_review.go',r'DELETE FROM images WHERE id=\?','UPDATE images SET version=version WHERE id=?','./internal/accounts','TestAvatarReviewDeletesCurrentImage'),
 ('anonymous attempt lifecycle','server/internal/accounts/code_flow.go',r'attempts=attempts\+1,closed=CASE WHEN attempts\+1>=3 THEN 1 ELSE 0 END','attempts=attempts,closed=0','./internal/accounts','TestAnonymousCodeFlowHTTPShapeAndThirdAttempt'),
 ('old inline rendition copy','server/internal/platform/media/legacy_renditions.go',r'SELECT image_id,file_name FROM legacy_image_renditions ORDER BY image_id,file_name','SELECT image_id,file_name FROM legacy_image_renditions WHERE 0 ORDER BY image_id,file_name','./internal/platform/media','TestLegacyInlineRenditionsReachIsolatedMedia'),
]
for index,(name,file,pattern,replacement,package,test) in enumerate(CASES):
 path=ROOT/file;original=path.read_text()
 damaged,count=re.subn(pattern,lambda _:replacement,original)
 if count!=1:raise RuntimeError(f'nonunique mutation {name}: {count}')
 log=Path('/tmp')/f'sjtuow-294-mutation-{index}.log'
 try:
  path.write_text(damaged)
  with log.open('w') as output:
   run=subprocess.run(['go','test',package,'-run',test,'-count=1'],cwd=ROOT/'server',stdout=output,stderr=subprocess.STDOUT,timeout=240)
  evidence=log.read_text()
  if run.returncode==0 or '--- FAIL:' not in evidence or 'build failed' in evidence:raise RuntimeError(f'probe did not fail assertions: {name}\n'+evidence[-2500:])
  print('MUTATION-CAUGHT '+name,flush=True)
 finally:path.write_text(original)
print('MUTATIONS-294-OK '+str(len(CASES)),flush=True)

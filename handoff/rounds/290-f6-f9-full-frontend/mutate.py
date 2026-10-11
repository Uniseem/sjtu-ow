"""Assertion-level mutations; run on the test host, restore even on failure."""
from pathlib import Path
import subprocess
root = Path(__file__).resolve().parents[3]
cases = [
 ("profile version prevents lost update", "accounts/profile_patch.go", "if u.Version != *in.BaseVersion {", "if false {", "accounts", "TestPersonalStaleProfile"),
 ("explicit null clears a rank", "accounts/personal_patch.go", "provided := ch.present[rank.name] || rank.value != nil", "provided := rank.value != nil", "accounts", "TestPersonalGamePatchNull"),
 ("private article owner boundary", "content/service.go", "return p.OwnerID != nil && *p.OwnerID == v.ID", "return true", "content", "TestRound290AuthorCannotRead"),
 ("preview actor boundary", "content/admin_preview.go", "if !ok || entry.OwnerID != viewer.ID {", "if !ok {", "content", "TestRound290MarkdownPreview"),
 ("preview expires", "content/admin_preview.go", "if ok && !entry.Expires.After(time.Now()) {", "if false {", "content", "TestRound290MarkdownPreview"),
 ("notification freezes recipients and content", "notify/notice_preview.go", "if !hmac.Equal([]byte(draft.preview.PreviewVersion), []byte(version)) {", "if hmac.Equal([]byte(draft.preview.PreviewVersion), []byte(version)) && false {", "notify", "TestConfirmedNoticeRejects"),
 ("broadcast replay cannot enqueue twice", "notify/announce.go", "if delivered.Valid {", "if false {", "notify", "TestWorkerBroadcastReplay"),
 ("font download rejects private networks", "fonts/google.go", "ip = ip.Unmap()", "return true\n//", "fonts", "TestPinnedDownloaderRejects"),
 ("offsite retention stays in own directory", "ops/offsite.go", 'name := strings.TrimPrefix(object.Key, prefix)', 'name := filepath.Base(object.Key)' , "ops", "TestPruneOffsiteOnlyDeletes"),
 ("scheduled mail count waits for actual delivery", "notify/notice_preview.go", "deliveredRecipients = 0", "deliveredRecipients = len(draft.people)", "notify", "TestScheduledNoticeRecords"),
 ("format edit invalidates concurrent board", "scrims/service.go", 'sets = append(sets, "board_version = board_version + 1")', 'sets = append(sets, "board_version = board_version")', "scrims", "TestFormatChangeRejects"),
 ("used game inputs invalidate only their scrim board", "../db/migrations/00028_scrim_pool_version.sql", "WHERE game_account_id = NEW.id AND user_id IN (OLD.user_id, NEW.user_id)", "WHERE 0 AND game_account_id = NEW.id AND user_id IN (OLD.user_id, NEW.user_id)", "scrims", "TestGameInputsInvalidate"),
 ("restore cannot change a contributor's protected comment setting", "content/admin_articles.go", "detail.Draft.CommentsEnabled = current.CommentsEnabled", "detail.Draft.CommentsEnabled = !current.CommentsEnabled", "content", "TestRestoreRevisionPreserves"),
 ("publication rechecks a closed category", "content/service.go", 'fields, err := s.validateArticleChanges(ctx, map[string]any{"category_id": *revContent.CategoryID})', 'fields, err := map[string][]string{}, error(nil)', "content", "TestRestoreAndPublishRecheck"),
]
for n,(name, relative,before,after,module,test) in enumerate(cases):
 path=root / "server/internal" / relative
 original=path.read_text()
 if original.count(before)!=1: raise RuntimeError("nonunique target: "+name)
 log=Path("/tmp/sjtuow-290-mutation-%d.log"%n)
 try:
  path.write_text(original.replace(before,after))
  with log.open("w") as output:
   result=subprocess.run(["go","test","./internal/"+module,"-run",test,"-count=1"],cwd=root/"server",stdout=output,stderr=subprocess.STDOUT,timeout=180)
  content=log.read_text()
  if result.returncode==0 or "--- FAIL:" not in content or "build failed" in content:
   raise RuntimeError("mutation escaped or failed compilation: "+name+"\n"+content[-4000:])
  print("MUTATION-CAUGHT "+name,flush=True)
 finally: path.write_text(original)
path=root/"web/apps/site/src/components/PageFrame.vue"
original=path.read_text()
before='provide("page-data", { ...toRaw(payload) })'
if original.count(before)!=1: raise RuntimeError("nonunique page scope")
try:
 path.write_text(original.replace(before,'provide("page-data", payload)'))
 log=Path("/tmp/sjtuow-290-mutation-page-scope.log")
 with log.open("w") as output:
  result=subprocess.run(["pnpm","exec","vitest","run","src/page-frame.test.ts"],cwd=root/"web/apps/site",stdout=output,stderr=subprocess.STDOUT,timeout=90)
 if result.returncode==0 or "FAIL" not in log.read_text() or "DataCloneError" not in log.read_text():
  raise RuntimeError("page scope mutation escaped or failed to build: "+log.read_text()[-3000:])
 print("MUTATION-CAUGHT page payload is isolated and cloneable",flush=True)
finally: path.write_text(original)
print("MUTATIONS-OK %d"%(len(cases)+1),flush=True)

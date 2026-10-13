import { expect, test } from "vitest"
import { actionLabel, objectLabel } from "./log-labels"

test("every imported and new audit action has a readable Chinese label", () => {
  const actions = [
    "wagtail.create", "wagtail.edit", "wagtail.delete", "wagtail.publish", "wagtail.unpublish", "wagtail.copy", "wagtail.move", "wagtail.revert",
    "tournaments.publish", "tournaments.finish", "tournaments.cancel", "tournaments.arrange", "scrims.publish", "scrims.finish", "scrims.cancel", "scrims.select", "scrims.generate", "scrims.save_teams",
    "teams.assign_captain", "teams.disband", "tournaments.announce", "scrims.announce", "articles.announce", "users.deactivate", "users.reactivate", "tournaments.notify_participants", "scrims.notify_participants",
    "user.update", "feature_rule.add", "feature_rule.delete", "role.restriction_add", "role.restriction_delete", "registration.export",
    "moderation.handle", "moderation.ask_author", "avatar.take_down", "site_settings.update", "backup_settings.update", "backup_settings.secret",
    "image.update", "image.delete", "collection.create", "collection.rename", "collection.delete", "font.face_add", "font.face_delete", "font.import", "font.delete",
    "typography.update", "page.save_draft", "page.publish", "home.save_draft", "home.publish", "news.save_draft", "news.publish",
  ]
  for (const action of actions) expect(actionLabel(action), action).not.toBe(action)
  for (const object of ["user", "team", "member_group", "article", "page", "home", "news", "tournament", "scrim", "registration", "comment", "site_settings", "backup_settings", "font", "typography", "image", "collection", "role", "moderation_item", "avatar_submission"]) {
    expect(objectLabel(object), object).not.toBe(object)
  }
})

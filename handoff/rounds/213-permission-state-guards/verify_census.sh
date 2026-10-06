set -u
run() {
  file="$1"; old="$2"; new="$3"; test="$4"
  cp "$file" /tmp/v213.bak
  python3 - "$file" "$old" "$new" <<'PY'
import sys
p, old, new = sys.argv[1], sys.argv[2], sys.argv[3]
s = open(p).read()
assert old in s, f"not found in {p}: {old!r}"
open(p, "w").write(s.replace(old, new, 1))
PY
  out=$(uv run pytest -q "$test" 2>&1 | tail -1)
  cp /tmp/v213.bak "$file"
  case "$out" in
    *failed*|*error*) echo "ok 抓到 $file :: $out";;
    *) echo "!! 没抓到 $file :: $out";;
  esac
}
run accounts/forms.py 'if qs.exists():
            raise ValidationError(BATTLTAG_TAKEN)' 'if False:
            raise ValidationError(BATTLTAG_TAKEN)' accounts/tests/test_me.py::test_a_taken_battletag_is_a_form_error_not_a_crash
run backoffice/views/articles.py 'if not parent.permissions_for_user(user).can_add_subpage():' 'if False:' backoffice/tests/test_backoffice.py::test_a_manager_without_submission_cannot_write_articles
run backoffice/views/articles.py 'if parent is None:' 'if False:' backoffice/tests/test_backoffice.py::test_article_new_without_an_index_is_404
run backoffice/views/images.py 'if error:
        return JsonResponse({"error": error}, status=400)' 'if False:
        return JsonResponse({"error": error}, status=400)' backoffice/tests/test_backoffice.py::test_the_chooser_reports_a_bad_file_instead_of_crashing
run core/held_views.py 'if not request.user.is_authenticated:
        raise Http404' 'if False:
        raise Http404' core/tests/test_held_letters.py::test_the_preview_is_404_for_anonymous
run core/announce_admin.py 'if entry is None:' 'if False:' core/tests/test_announcements.py::test_an_unknown_kind_is_404
run backoffice/nav.py 'if section not in BY_KEY:' 'if False:' backoffice/tests/test_door.py::test_a_section_that_does_not_exist_is_caught_when_the_page_is_placed
run tournaments/services.py 'if tournament.status == TournamentStatus.DRAFT and missing(tournament):' 'if False:' tournaments/tests/test_tournaments.py::test_a_half_filled_draft_is_deleted_not_cancelled

package notify

import (
	"context"
	"database/sql"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"sort"
	"strings"

	"github.com/Uniseem/sjtu-ow/server/internal/platform/db"
)

// ImportLegacyHeldLetters copies core.HeldLetter's frozen records after account
// import. The supplied legacy database must be opened read-only by the caller.
// It never sends mail, creates jobs, refreshes dates or resets decided states.
func ImportLegacyHeldLetters(ctx context.Context, target *db.DB, legacy *sql.DB) error {
	var exists int
	if err := legacy.QueryRowContext(ctx, "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='core_heldletter'").Scan(&exists); err != nil {
		return fmt.Errorf("检查旧待发信表: %w", err)
	}
	// Backups before migration core/0023 have no held-letter feature.
	if exists == 0 {
		return nil
	}
	if err := checkLegacyHeldColumns(ctx, legacy); err != nil {
		return err
	}
	rows, err := legacy.QueryContext(ctx, `SELECT id,batch,actor_id,letter,recipients,back,in_back_office,state,created_at,decided_at
        FROM core_heldletter ORDER BY id`)
	if err != nil {
		return fmt.Errorf("读取旧待发信: %w", err)
	}
	defer rows.Close()
	return target.WriteTx(ctx, func(txCtx context.Context, tx *db.Tx) error {
		for rows.Next() {
			var id, actor int64
			var batch, letter, recipients, back, state, created string
			var inBack int
			var decided sql.NullString
			if err := rows.Scan(&id, &batch, &actor, &letter, &recipients, &back, &inBack, &state, &created, &decided); err != nil {
				return fmt.Errorf("读取旧待发信字段: %w", err)
			}
			invalid := func(field string) error {
				return fmt.Errorf("旧待发信%d的%s无效，未导入任何本批记录", id, field)
			}
			if id <= 0 || actor <= 0 {
				return invalid("编号或操作人")
			}
			normalized, err := legacyHeldBatch(batch)
			if err != nil {
				return invalid("UUID批次")
			}
			if state != "waiting" && state != "sent" && state != "skipped" {
				return invalid("状态")
			}
			if inBack != 0 && inBack != 1 {
				return invalid("后台标记")
			}
			stamp, err := db.ParseUTC(created)
			if err != nil || stamp.IsZero() {
				return invalid("创建时间")
			}
			decidedStamp := ""
			if decided.Valid && decided.String != "" {
				at, err := db.ParseUTC(decided.String)
				if err != nil || at.IsZero() {
					return invalid("决定时间")
				}
				decidedStamp = db.FormatUTC(at)
			}
			if err := validateLegacyHeldLetter(letter); err != nil {
				return invalid("冻结信结构（" + err.Error() + "）")
			}
			if err := validateLegacyHeldRecipients(recipients); err != nil {
				return invalid("冻结收件人结构")
			}
			var knownActor int
			if err := tx.QueryRowContext(txCtx, "SELECT COUNT(*) FROM users WHERE id=?", actor).Scan(&knownActor); err != nil {
				return err
			}
			if knownActor != 1 {
				return fmt.Errorf("旧待发信%d的操作人未导入；先完成账号导入", id)
			}
			// Existing same-origin rows are immutable except for decisions.
			// A numeric collision with another actor/batch cannot be ignored.
			var oldActor int64
			var oldBatch, oldLetter, oldRecipients string
			err = tx.QueryRowContext(txCtx, "SELECT actor_id,batch,letter,recipients FROM held_letters WHERE id=?", id).Scan(&oldActor, &oldBatch, &oldLetter, &oldRecipients)
			if err == nil {
				if oldActor != actor || oldBatch != normalized || !sameFrozenJSON(oldLetter, letter) || !sameFrozenJSON(oldRecipients, recipients) {
					return fmt.Errorf("待发信编号%d与新库已有冻结记录冲突，停止导入", id)
				}
				// Preserve any decision made in the new stack between imports.
				continue
			}
			if !errors.Is(err, sql.ErrNoRows) {
				return err
			}
			if _, err := tx.ExecContext(txCtx, `INSERT INTO held_letters
                (id,batch,actor_id,letter,recipients,back,in_back_office,state,created_at,decided_at)
                VALUES(?,?,?,?,?,?,?,?,?,?)`, id, normalized, actor, letter, recipients, back, inBack, state, db.FormatUTC(stamp), decidedStamp); err != nil {
				return fmt.Errorf("写入旧待发信%d: %w", id, err)
			}
		}
		if err := rows.Err(); err != nil {
			return fmt.Errorf("读取旧待发信: %w", err)
		}
		return nil
	})
}

func checkLegacyHeldColumns(ctx context.Context, legacy *sql.DB) error {
	rows, err := legacy.QueryContext(ctx, "PRAGMA table_info(core_heldletter)")
	if err != nil {
		return fmt.Errorf("读取旧待发信结构: %w", err)
	}
	defer rows.Close()
	columns := map[string]bool{}
	for rows.Next() {
		var index, notNull, primary int
		var name, kind string
		var fallback any
		if err := rows.Scan(&index, &name, &kind, &notNull, &fallback, &primary); err != nil {
			return err
		}
		columns[name] = true
	}
	if err := rows.Err(); err != nil {
		return err
	}
	missing := []string{}
	for _, name := range []string{"id", "batch", "actor_id", "letter", "recipients", "back", "in_back_office", "state", "created_at", "decided_at"} {
		if !columns[name] {
			missing = append(missing, name)
		}
	}
	if len(missing) > 0 {
		sort.Strings(missing)
		return fmt.Errorf("旧待发信表缺少实际模型字段: %s", strings.Join(missing, ", "))
	}
	return nil
}

// Django stores UUIDField as 32 hex digits in SQLite, but its <uuid:...> links
// render the same identifier in 36-character canonical form. Go accepts both
// in string path params; importing the canonical form preserves old URLs.
func legacyHeldBatch(value string) (string, error) {
	raw := strings.ToLower(value)
	if len(raw) == 36 {
		for _, index := range []int{8, 13, 18, 23} {
			if raw[index] != '-' {
				return "", fmt.Errorf("UUID分隔符无效")
			}
		}
		raw = strings.ReplaceAll(raw, "-", "")
	}
	if len(raw) != 32 {
		return "", fmt.Errorf("UUID长度无效")
	}
	if _, err := hex.DecodeString(raw); err != nil {
		return "", err
	}
	return raw[:8] + "-" + raw[8:12] + "-" + raw[12:16] + "-" + raw[16:20] + "-" + raw[20:], nil
}

func legacyText(raw json.RawMessage) bool {
	if string(raw) == "null" {
		return false
	}
	var text string
	return json.Unmarshal(raw, &text) == nil
}

func legacyPairs(raw json.RawMessage) bool {
	if string(raw) == "null" {
		return false
	}
	var pairs []json.RawMessage
	if json.Unmarshal(raw, &pairs) != nil {
		return false
	}
	for _, rawPair := range pairs {
		var pair []json.RawMessage
		if json.Unmarshal(rawPair, &pair) != nil || len(pair) != 2 || !legacyText(pair[0]) || !legacyText(pair[1]) {
			return false
		}
	}
	return true
}

func validateLegacyHeldRecipients(raw string) error {
	if !legacyPairs(json.RawMessage(raw)) {
		return fmt.Errorf("收件人不是地址和昵称二元组")
	}
	return nil
}

func validateLegacyHeldLetter(raw string) error {
	var object map[string]json.RawMessage
	if json.Unmarshal([]byte(raw), &object) != nil || object == nil {
		return fmt.Errorf("信不是JSON对象")
	}
	for _, required := range []string{"subject", "lead"} {
		field, exists := object[required]
		if !exists || !legacyText(field) {
			return fmt.Errorf("缺少%s文本", required)
		}
	}
	for _, name := range []string{"item_link", "code", "note", "reason", "unsubscribe", "notice"} {
		if field, exists := object[name]; exists && !legacyText(field) {
			return fmt.Errorf("%s不是文本", name)
		}
	}
	for _, name := range []string{"facts", "items"} {
		if field, exists := object[name]; exists && !legacyPairs(field) {
			return fmt.Errorf("%s不是二元组列表", name)
		}
	}
	if field, exists := object["paragraphs"]; exists {
		if string(field) == "null" {
			return fmt.Errorf("paragraphs不是文本列表")
		}
		var values []json.RawMessage
		if json.Unmarshal(field, &values) != nil {
			return fmt.Errorf("paragraphs不是文本列表")
		}
		for _, value := range values {
			if !legacyText(value) {
				return fmt.Errorf("paragraphs含非文本")
			}
		}
	}
	if field, exists := object["action"]; exists && string(field) != "null" {
		var values []json.RawMessage
		if json.Unmarshal(field, &values) != nil || len(values) != 2 || !legacyText(values[0]) || !legacyText(values[1]) {
			return fmt.Errorf("action不是按钮文字和地址二元组")
		}
	}
	// Unknown historic keys stay in the original JSON, matching Python thaw's
	// ignored-key behavior without destructively rewriting a frozen document.
	return nil
}

func sameFrozenJSON(left, right string) bool {
	var a, b any
	if json.Unmarshal([]byte(left), &a) != nil || json.Unmarshal([]byte(right), &b) != nil {
		return false
	}
	encodedA, err := json.Marshal(a)
	if err != nil {
		return false
	}
	encodedB, err := json.Marshal(b)
	if err != nil {
		return false
	}
	return string(encodedA) == string(encodedB)
}

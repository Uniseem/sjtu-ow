-- 00001 空基线（222 轮）。M1 只立迁移机制；第一个领域表在各自的里程碑加
-- （M3 账号起）。迁移的幂等和版本表由 internal/platform/db 的测试验证。

-- +goose Up
SELECT 1;

-- +goose Down
SELECT 1;

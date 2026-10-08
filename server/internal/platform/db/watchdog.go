package db

import "time"

// watchdog 记写事务的两个阈值（12 号文档 5.6）。两个数这轮都是拍脑袋的，
// 最终数值等导入后的真实事务时长分布再定（13 号文档 C 节）。
type watchdog struct {
	failAfter time.Duration // 超过就回滚并报错，到点先取消 ctx；0 关。开发和测试 1 秒
	warnAfter time.Duration // 超过提交完只记警告，不影响事务；0 关。生产 200 毫秒
}

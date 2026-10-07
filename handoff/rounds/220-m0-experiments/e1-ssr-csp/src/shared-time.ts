// One way to show a time, the same string on the server and in the browser
// whatever either one's time zone is (12-architecture 6.3).
const fmt = new Intl.DateTimeFormat("zh-CN", {
  timeZone: "Asia/Shanghai",
  year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", hour12: false,
});
export const showTime = (iso: string) => fmt.format(new Date(iso));

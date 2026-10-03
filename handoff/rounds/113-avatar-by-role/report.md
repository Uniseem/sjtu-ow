# 113 默认头像按主位置配英雄（报告）

## 做了什么

1. **设计 v6.10**：细节 2.4 加「按主位置」一条、「速度」一条改成多查一次顶层文件夹，版本 v6.9 → v6.10；`design.md` 版本和附录 D
2. **`core/avatars.py`**：
   - `load_pool()` 自己查（不再借 `covers.load_pool`）：图连同所在集合一起取（`select_related`），再查一次图库下面的顶层文件夹，给每张图标上 `face_role`：在「坦克」「输出」「支援」（和主位置的叫法一样，`ROLE_BY_FOLDER`）或它们的子文件夹里的标对应位置，其余标空
   - `position(person)`：主位置；没填就用「也能打」里排在最前的（坦克、输出、支援的顺序）；都没填是空
   - `pick()`：有位置的人先在同位置的图里按 `ID mod 张数` 取；没位置、或这个位置一张图也没有，从整个图库取
3. **测试**：`accounts/tests/test_default_avatar.py` 加 6 条（共 18 条）
4. **本机和演示站**：`sort_faces.py` 按官网英雄列表页每张卡片的 `data-role` 把 53 张头像移进三个文件夹：坦克 15、输出 24、支援 14
5. 没改 README：111 那条说的「子集合也算」仍然对，文件夹名字的规则写在设计里

## 中途改过一次规则

先按「主位置，没填就看『也能打』是不是只有一个位置」写的。演示站上一查：Mercy不奶没填主位置、「也能打」是坦克和输出，成员小卡上只显示「坦克」，头像却从整个图库取到了堡垒，和卡片对不上。看了 `play_style.html`：小卡（`compact`）只显示 `profile.roles` 的第一个，就是主位置，没有就是「也能打」里排在最前的。改成头像跟着这个位置走，设计、请求、测试和变异一起改了。

## 命令输出

变异（`mutate.py`，8 处）。第一版漏了两处：「没位置只给第一张图」「子文件夹的图不算」，测试里只有一个人，`ID mod 张数` 碰巧落在对的图上；改成连号的两三个人（换哪种错法都至少有一个人拿错），重跑：

```
baseline green, 6 tests
caught the position is ignored -> test_a_tank_gets_a_tank_face_and_a_support_a_support_face
caught no main position means no face -> test_without_a_main_position_any_face
caught an empty position folder breaks the page -> test_an_empty_position_folder_falls_back_to_the_whole_pool
caught only faces right in the position folder count -> test_folders_under_a_position_folder_count_for_it
caught folders are matched by the wrong name -> test_a_tank_gets_a_tank_face_and_a_support_a_support_face
caught the other positions are ignored -> test_without_a_main_position_the_first_other_one_counts
caught the last other position is used -> test_without_a_main_position_the_first_other_one_counts
caught each face looks its folder up -> test_loading_the_pool_costs_the_same_however_many_faces
restored and green; missed: none
```

整组检查（开发服务器停着）：

```
All checks passed!
276 files already formatted
Built production stylesheet 'D:\claude\sjtu-ow\static\css\app.css'.
No changes detected
System check identified no issues (0 silenced).
```

```
1295 passed in 149.31s (0:02:29)
```

官网英雄位置（`overwatch.blizzard.com/en-us/heroes/`）：

```
53 missing: [] extra: []
Counter({'damage': 24, 'tank': 15, 'support': 14})
```

本机和演示站分文件夹：

```
in folders: {'支援': 14, '输出': 24, '坦克': 15} | left loose: 0
```

演示站（最后一次镜像时间 `2026-10-03T12:14:16+02:00`）全量生成 46 页成功。没有头像的 20 个演示用户，位置和分到的英雄：

```
2 老周 输出 -> 堡垒 输出
4 Mercy不奶 坦克 -> 骇灾 坦克
6 雨后彩虹 支援 -> 雾子 支援
8 无名小卒 输出 -> 半藏 输出
10 球球 输出 -> 美 输出
12 小卢 输出 -> 死神 输出
14 盾墙 支援 -> 安娜 支援
16 叶卡 支援 -> 布丽吉塔 支援
18 大锤 支援 -> 火箭猫 支援
20 东川路车神 支援 -> 雾子 支援
22 Soldier76 输出 -> 探奇 输出
24 糖豆 输出 -> 安燃 输出
26 黑百合 支援 -> 无漾 支援
28 小天使 坦克 -> 破坏球 坦克
30 卡西迪 输出 -> 弗蕾娅 输出
32 咩咩 支援 -> 火箭猫 支援
34 慢热型选手 输出 -> 美 输出
36 布丽吉塔 输出 -> 死神 输出
38 星河 坦克 -> 拉玛刹 坦克
40 Moira 输出 -> 士兵：76 输出
```

成员展示页截图：小卡上的位置和头像的英雄对得上。

## 没做 / 未验证

- 同一位置里不看英雄偏好（主玩天使的人不一定分到天使），也没有让用户自己选
- 同位置的人数比图多时会重复（演示站雾子、火箭猫、美、死神各两人）

<script setup lang="ts">
import { useViewer } from "../viewer"
import { shanghaiYear } from "../time"
import BrandMark from "./BrandMark.vue"

// The footer (design 13.2.7): who runs the site, the link columns (the
// account column follows the viewer), the base row.
const viewer = useViewer()
const user = viewer.user
</script>
<template>
  <footer class="c-footer">
    <div class="l-container">
      <div class="c-footer__grid">
        <div>
          <BrandMark />
          <p class="c-footer__statement">
            SJTU-OW 是上海交通大学守望先锋玩家的社团网站，由学生社团自己建设和维护。不是上海交通大学官方网站，与游戏开发商、运营商无关。
          </p>
        </div>
        <div class="c-footer__links">
          <nav class="c-footer__col font-nav" aria-label="社区">
            <h2 class="c-eyebrow">社区</h2>
            <a href="/news/">社区资讯</a>
            <a href="/members/">成员展示</a>
            <a href="/teams/">战队</a>
          </nav>
          <nav class="c-footer__col font-nav" aria-label="参与">
            <h2 class="c-eyebrow">参与</h2>
            <a href="/tournaments/">赛事</a>
            <a href="/scrims/">内战</a>
            <a href="/submit/">我要投稿</a>
          </nav>
          <nav class="c-footer__col font-nav" aria-label="账号">
            <h2 class="c-eyebrow">账号</h2>
            <template v-if="user">
              <a v-if="user.admin" href="/admin/" data-admin-link>管理后台</a>
              <a href="/me/">个人中心</a>
              <a href="/me/registrations/">我的报名</a>
              <a href="/me/teams/">我的战队</a>
            </template>
            <template v-else>
              <a href="/accounts/login/">登录</a>
              <a href="/accounts/signup/">注册</a>
            </template>
          </nav>
          <nav class="c-footer__col font-nav" aria-label="关于本站">
            <h2 class="c-eyebrow">关于</h2>
            <a href="/about/">关于我们</a>
            <a href="/terms/">用户协议</a>
            <a href="/privacy/">隐私政策</a>
          </nav>
        </div>
      </div>
      <div class="c-footer__base">
        <span>© {{ shanghaiYear() }} SJTU-OW · 学生社团自办网站</span>
        <span>不是上海交通大学官方网站 · 与游戏开发商、运营商无关 · 游戏图片版权归暴雪娱乐所有</span>
      </div>
    </div>
  </footer>
</template>

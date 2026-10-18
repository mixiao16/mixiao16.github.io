# yinghanart.com — Yinghan Zhang 作品集网站

石头艺术家 · 版画家 张樱瀚(Yinghan Zhang)的个人作品集。纯静态网站(无需服务器、无需数据库),托管在 GitHub Pages,域名 **https://yinghanart.com**。

A static portfolio (HTML/CSS/JS, no framework, no tracking) for Yinghan Zhang, hosted on GitHub Pages.

## 网站结构

| 页面 | 地址 | 说明 |
|---|---|---|
| 首页 | `/` | 「拓印揭示」互动首屏(用鼠标/手指拂去纸面,拓出石形)、图版横滑 / 目录两种浏览方式、《静观》创作过程红线图 |
| 作品页 | `/works/<作品名>/` | 大图、点击灯箱放大(滚轮 / 双指缩放 / 拖拽 / 键盘左右键)、鼠标悬停放大镜 |
| 关于 | `/about/` | 艺术家简介(中英双语) |
| 联系 | `/contact/` | Instagram、邮箱、当地时间 |

- 右上角可切换 **中文 / English**、**纸 / 墨**(浅色 / 深色)。
- 手机、平板、电脑均已适配;键盘可操作;支持「减少动态效果」系统设置。

## 如何更新内容(最简单:直接告诉 Claude)

在这个 Project 里对 Claude 说,例如:
- 「新增一件作品《xxx》,图片在 art/xxx 文件夹」
- 「把《Hug》的年份写成 2024,媒介是木刻拓印」
- 「把联系邮箱改成 xxx@xxx.com」
Claude 会修改数据、重新生成网站并推送到 GitHub,几分钟内线上生效。

## 手动更新(进阶)

所有文字和作品信息都在 `data/works.json`:

```jsonc
{ "slug": "hug", "title": "Hug", "title_zh": "拥抱",
  "year": 2024, "medium": "Woodcut rubbing", "medium_zh": "木刻拓印", "size": "24 × 36 in",
  "images": [ { "src": "Hug/IMG_6414.jpg", "alt": "…", "alt_zh": "…" } ] }
```

```bash
# 1) 把原图转成网页用的多尺寸 WebP(只处理新增的图片)
python3 tools/process_images.py --art "<你的 art 文件夹>" --site .
# 2) 生成分享图 + 页面 + CSS/JS
python3 tools/make_og.py && python3 tools/build.py
# 3) 如果新增了中文文字,重新生成中文字体子集(很快)
python3 tools/subset_zh.py --src <@fontsource/noto-serif-sc 目录>
# 4) 本地预览
python3 -m http.server 8000      # 打开 http://localhost:8000
# 5) 发布
git add -A && git commit -m "update" && git push
```

依赖:Python 3 + Pillow + fonttools + brotli(`pip install pillow fonttools brotli`)。

## 目录

```
index.html, about/, contact/, works/<slug>/   生成出来的页面(不要手改,会被覆盖)
assets/css/site.css, assets/js/main.js        由 tools/src/ 合并生成
assets/img/<slug>/                            响应式图片;assets/fonts/ 字体;assets/video/ 视频;assets/og/ 分享图
data/works.json                               内容数据(手改这里)
tools/                                        build.py · process_images.py · make_og.py · subset_zh.py · src/(CSS 与 JS 源码)
CNAME, .nojekyll, 404.html, sitemap.xml, robots.txt
```

## 域名与托管

- 仓库:`mixiao16/mixiao16.github.io`(GitHub 用户站点),Pages 从 `main` 分支根目录发布。
- `CNAME` 文件内容为 `yinghanart.com`。DNS(在域名注册商处设置):
  - `A` 记录 `@` → `185.199.108.153`、`185.199.109.153`、`185.199.110.153`、`185.199.111.153`
  - `CNAME` 记录 `www` → `mixiao16.github.io`
- GitHub → Settings → Pages 里勾选 **Enforce HTTPS**。

## 字体与致谢

Cormorant Garamond、DM Mono、Noto Serif SC(均为 SIL Open Font License,经 Fontsource 获取;中文为按本站用字裁剪的子集)。

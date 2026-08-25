"""data/postings.json 을 읽어 전체 공고 열람 페이지(docs/index.html)를 만든다.

외부 리소스를 하나도 쓰지 않는 단일 HTML 이라 GitHub Pages 에 그대로 올라간다.
검색·직군 필터·정렬은 전부 페이지 안에서 처리한다.

    python build_site.py
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

SRC = Path("data/postings.json")
OUT = Path("docs/index.html")
KST = timezone(timedelta(hours=9))

CATEGORY_ORDER = ["기획", "클라이언트", "서버", "아트"]
SOURCE_LABEL = {
    "gamejob": "게임잡",
    "wanted": "원티드",
    "saramin": "사람인",
    "jobkorea": "잡코리아",
}

TEMPLATE = """<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex">
<title>게임 개발자 채용공고</title>
<style>
:root{color-scheme:light dark;--bg:#fff;--fg:#1a1a1a;--muted:#6b6b6b;--line:#e3e3e3;
--card:#fafafa;--accent:#3b6ef0;--chip:#eef1f7;--new:#e8f5e9;--new-fg:#1b5e20}
@media(prefers-color-scheme:dark){:root{--bg:#16171a;--fg:#e8e8e8;--muted:#9a9a9a;
--line:#2c2e33;--card:#1d1f23;--accent:#7aa2ff;--chip:#26282e;--new:#1e3a22;--new-fg:#a5d6a7}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);
font:15px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI","Malgun Gothic",sans-serif}
.wrap{max-width:960px;margin:0 auto;padding:20px 16px 64px}
h1{font-size:20px;font-weight:600;margin:0 0 4px}
.sub{color:var(--muted);font-size:13px;margin-bottom:18px}
.controls{position:sticky;top:0;background:var(--bg);padding:10px 0;border-bottom:1px solid var(--line);z-index:5}
.tabs{display:flex;gap:6px;flex-wrap:wrap;margin-bottom:8px}
.tab{border:1px solid var(--line);background:var(--card);color:var(--fg);border-radius:999px;
padding:6px 14px;font-size:13px;cursor:pointer;font-family:inherit}
.tab[aria-pressed=true]{background:var(--accent);border-color:var(--accent);color:#fff}
.row2{display:flex;gap:8px;flex-wrap:wrap}
input[type=search],select{border:1px solid var(--line);background:var(--card);color:var(--fg);
border-radius:8px;padding:8px 10px;font-size:14px;font-family:inherit}
input[type=search]{flex:1;min-width:180px}
label.chk{display:flex;align-items:center;gap:5px;font-size:13px;color:var(--muted);cursor:pointer}
#count{color:var(--muted);font-size:13px;margin:14px 0 8px}
.job{border-bottom:1px solid var(--line);padding:12px 2px}
.job a{color:var(--accent);text-decoration:none;font-weight:500}
.job a:hover{text-decoration:underline}
.meta{color:var(--muted);font-size:13px;margin-top:3px;display:flex;gap:6px;flex-wrap:wrap;align-items:center}
.chip{background:var(--chip);border-radius:5px;padding:1px 7px;font-size:12px}
.new{background:var(--new);color:var(--new-fg);border-radius:5px;padding:1px 7px;font-size:12px;font-weight:600}
.empty{color:var(--muted);padding:40px 0;text-align:center}
</style>
</head>
<body>
<div class="wrap">
<h1>게임 개발자 채용공고</h1>
<div class="sub">신입 · 인턴 · 경력무관 · 3년 이하 &nbsp;·&nbsp; __COUNT__건 &nbsp;·&nbsp; __UPDATED__ 갱신</div>

<div class="controls">
  <div class="tabs" id="tabs"></div>
  <div class="row2">
    <input type="search" id="q" placeholder="회사, 공고명, 지역 검색">
    <select id="sort">
      <option value="cat">직군순</option>
      <option value="years">경력 낮은순</option>
      <option value="company">회사명순</option>
    </select>
    <label class="chk"><input type="checkbox" id="onlynew"> 오늘 신규만</label>
  </div>
</div>

<div id="count"></div>
<div id="list"></div>
</div>

<script id="data" type="application/json">__DATA__</script>
<script>
var JOBS = JSON.parse(document.getElementById('data').textContent);
var CATS = __CATS__;
var SRC  = __SRCS__;
var params = new URLSearchParams(location.search);
var wanted = params.get('cat');
var cat = (wanted && CATS.indexOf(wanted) >= 0) ? wanted : '전체';
var q = '', sort = 'cat', onlynew = false;

var tabs = document.getElementById('tabs');
['전체'].concat(CATS).forEach(function(c){
  var b = document.createElement('button');
  b.className = 'tab'; b.textContent = c;
  b.setAttribute('aria-pressed', c === cat);
  b.onclick = function(){
    cat = c;
    Array.prototype.forEach.call(tabs.children, function(x){
      x.setAttribute('aria-pressed', x === b);
    });
    render();
  };
  tabs.appendChild(b);
});

document.getElementById('q').oninput = function(e){ q = e.target.value.toLowerCase(); render(); };
document.getElementById('sort').onchange = function(e){ sort = e.target.value; render(); };
document.getElementById('onlynew').onchange = function(e){ onlynew = e.target.checked; render(); };

function esc(s){ return String(s == null ? '' : s).replace(/[&<>"]/g, function(m){
  return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[m]; }); }

function render(){
  var rows = JOBS.filter(function(j){
    if (cat !== '전체' && j.category !== cat) return false;
    if (onlynew && !j.new) return false;
    if (!q) return true;
    return (j.title + ' ' + j.company + ' ' + (j.location||'')).toLowerCase().indexOf(q) >= 0;
  });

  if (sort === 'years') {
    rows.sort(function(a,b){ return (a.years==null?99:a.years) - (b.years==null?99:b.years); });
  } else if (sort === 'company') {
    rows.sort(function(a,b){ return a.company.localeCompare(b.company, 'ko'); });
  } else {
    rows.sort(function(a,b){
      var d = CATS.indexOf(a.category) - CATS.indexOf(b.category);
      if (d) return d;
      return (a.years==null?99:a.years) - (b.years==null?99:b.years);
    });
  }

  document.getElementById('count').textContent = rows.length + '건';
  var list = document.getElementById('list');
  if (!rows.length){ list.innerHTML = '<div class="empty">조건에 맞는 공고가 없습니다.</div>'; return; }

  list.innerHTML = rows.map(function(j){
    var bits = [];
    if (j.new) bits.push('<span class="new">NEW</span>');
    bits.push('<span class="chip">' + esc(j.category) + '</span>');
    if (j.career)   bits.push(esc(j.career));
    if (j.location) bits.push(esc(j.location));
    if (j.deadline) bits.push('~ ' + esc(j.deadline));
    bits.push('<span class="chip">' + esc(SRC[j.source] || j.source) + '</span>');
    return '<div class="job"><a href="' + esc(j.url) + '" target="_blank" rel="noopener">'
      + esc(j.title) + '</a><div class="meta"><strong style="color:var(--fg);font-weight:500">'
      + esc(j.company) + '</strong>' + bits.join(' · ') + '</div></div>';
  }).join('');
}
render();
</script>
</body>
</html>
"""


def main() -> int:
    if not SRC.exists():
        print(f"{SRC} 가 없습니다. run_once.py 를 먼저 실행해 주세요.")
        return 1

    data = json.loads(SRC.read_text(encoding="utf-8"))
    postings = data["postings"]

    updated = datetime.fromisoformat(data["updated"]).astimezone(KST)
    html = (
        TEMPLATE
        .replace("__DATA__", json.dumps(postings, ensure_ascii=False, separators=(",", ":")))
        .replace("__CATS__", json.dumps(CATEGORY_ORDER, ensure_ascii=False))
        .replace("__SRCS__", json.dumps(SOURCE_LABEL, ensure_ascii=False))
        .replace("__COUNT__", f"{len(postings):,}")
        .replace("__UPDATED__", updated.strftime("%Y-%m-%d %H:%M KST"))
    )

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(html, encoding="utf-8")
    size = OUT.stat().st_size / 1024
    new = sum(1 for p in postings if p.get("new"))
    print(f"{OUT} 생성 ({size:.0f} KB, {len(postings)}건, 신규 {new}건)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

async function get(path) {
  const r = await fetch(path);
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}
async function post(path, body) {
  const r = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: body === undefined ? "{}" : JSON.stringify(body ?? {}),
  });
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}
function 徽(v) {
  const s = String(v);
  if (s === "对齐" || s === "1" || s === "true" || s.includes("已入")) return `<span class="徽 绿">${s}</span>`;
  if (s.includes("缺") || s.includes("不符") || s === "0" || s === "false") return `<span class="徽 红">${s}</span>`;
  return `<span class="徽 灰">${s}</span>`;
}
function 表(headers, rows, mapRow) {
  if (!rows || !rows.length) return '<div class="空">暂无数据</div>';
  return `<div class="表绕"><table><thead><tr>${headers.map(h=>`<th>${h}</th>`).join("")}</tr></thead>
    <tbody>${rows.map(r=>`<tr>${mapRow(r)}</tr>`).join("")}</tbody></table></div>`;
}
function 统计(items) {
  return `<div class="统计">${items.map(([n,v])=>`<div class="格"><div class="数">${v}</div><div class="名">${n}</div></div>`).join("")}</div>`;
}

// Road Wizdom frontend — vanilla JS + Leaflet
const BKK = [13.7563, 100.5018];

// ---------- Tabs ----------
document.querySelectorAll(".tab").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".tab").forEach((b) => b.classList.remove("active"));
    document.querySelectorAll(".panel").forEach((p) => p.classList.remove("active"));
    btn.classList.add("active");
    document.getElementById("tab-" + btn.dataset.tab).classList.add("active");
    if (btn.dataset.tab === "dashboard") loadDashboard();
    if (btn.dataset.tab === "analytics") loadAnalytics();
    // Leaflet needs a resize kick when its container becomes visible
    setTimeout(() => { reportMap.invalidateSize(); dashMap.invalidateSize(); }, 50);
  });
});

function riskClass(level) {
  return { "สูงมาก": "r4", "สูง": "r3", "ปานกลาง": "r2", "ต่ำ": "r1" }[level] || "r1";
}

// ---------- Report tab ----------
const reportMap = L.map("report-map").setView(BKK, 12);
L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
  attribution: "&copy; OpenStreetMap",
}).addTo(reportMap);

let picked = null;
let pickedMarker = null;
reportMap.on("click", (e) => {
  picked = e.latlng;
  if (pickedMarker) pickedMarker.remove();
  pickedMarker = L.marker(picked).addTo(reportMap);
  document.getElementById("coords").textContent =
    `ตำแหน่งที่เลือก: ${picked.lat.toFixed(5)}, ${picked.lng.toFixed(5)}`;
});

async function loadCategories() {
  const cats = await (await fetch("/api/categories")).json();
  const sel = document.getElementById("category");
  sel.innerHTML = cats.map((c) => `<option value="${c.key}">${c.th}</option>`).join("");
}
loadCategories();

document.getElementById("report-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  if (!picked) { alert("กรุณาแตะบนแผนที่เพื่อเลือกตำแหน่งก่อนครับ"); return; }
  const fd = new FormData();
  fd.append("category", document.getElementById("category").value);
  fd.append("description", document.getElementById("description").value);
  fd.append("lat", picked.lat);
  fd.append("lng", picked.lng);
  const photo = document.getElementById("photo").files[0];
  if (photo) fd.append("photo", photo);

  const res = await (await fetch("/api/reports", { method: "POST", body: fd })).json();
  const box = document.getElementById("report-result");
  box.classList.remove("hidden", "merged");
  if (res.merged) box.classList.add("merged");
  box.innerHTML = `
    <strong>${res.merged
      ? "🔁 AI ตรวจพบว่าเป็นเหตุการณ์เดียวกับเคสที่มีอยู่ — รวมรายงานให้แล้ว"
      : "✅ เปิดเคสใหม่เรียบร้อย"}</strong><br/>
    เคส #${res.case_id} · Risk Score <strong>${res.risk_score}</strong> (${res.risk_level})
    · ผู้ได้รับผลกระทบ ${res.impacted_count} ราย<br/>
    <em>AI Description:</em> ${res.ai_description}`;
  e.target.reset();
});

// ---------- Dashboard tab ----------
const dashMap = L.map("dash-map").setView(BKK, 11);
L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
  attribution: "&copy; OpenStreetMap",
}).addTo(dashMap);
let dashMarkers = [];

async function loadDashboard() {
  const cases = await (await fetch("/api/cases")).json();
  const list = document.getElementById("case-list");
  list.innerHTML = cases.map((c) => `
    <div class="case-card" onclick="openCase(${c.id})">
      <div class="row">
        <span class="title">#${c.id} ${c.category_th}</span>
        <span class="badge ${riskClass(c.risk_level)}">Risk ${c.risk_score} · ${c.risk_level}</span>
      </div>
      <div class="meta">
        <span class="badge ${c.status === "resolved" ? "resolved" : "status"}">${c.status_th}</span>
        ผู้ได้รับผลกระทบ ${c.impacted_count} ราย · อัปเดต ${c.updated_at.replace("T", " ")}
      </div>
    </div>`).join("") || "<p>ยังไม่มีเคส — ลองแจ้งปัญหาหรือรัน seed ก่อน</p>";

  dashMarkers.forEach((m) => m.remove());
  dashMarkers = cases.filter((c) => c.status !== "resolved").map((c) =>
    L.circleMarker([c.lat, c.lng], {
      radius: 6 + c.risk_score / 12,
      color: c.risk_score >= 80 ? "#c62828" : c.risk_score >= 65 ? "#e65100" : "#1565c0",
      fillOpacity: 0.6,
    }).addTo(dashMap).bindPopup(`#${c.id} ${c.category_th}<br/>Risk ${c.risk_score}`)
      .on("click", () => openCase(c.id))
  );
}

async function openCase(id) {
  const c = await (await fetch(`/api/cases/${id}`)).json();
  const box = document.getElementById("case-detail");
  box.classList.remove("hidden");
  box.innerHTML = `
    <h3>เคส #${c.id} — ${c.category_th}</h3>
    <span class="badge ${riskClass(c.risk_level)}">Risk ${c.risk_score} · ${c.risk_level}</span>
    <span class="badge ${c.status === "resolved" ? "resolved" : "status"}">${c.status_th}</span>
    <p class="meta" style="margin:8px 0">ผู้ได้รับผลกระทบ ${c.impacted_count} ราย · รายงานทั้งหมด ${c.reports.length} ฉบับ</p>
    ${c.reports.map((r) => `
      <p style="font-size:.86rem;margin:4px 0">📝 ${r.ai_description}</p>
      ${r.photo_path ? `<img src="${r.photo_path}" style="max-width:180px;border-radius:8px;margin:4px 0"/>` : ""}
    `).join("")}
    <h3 style="margin-top:12px">Timeline</h3>
    <div class="timeline">
      ${c.timeline.map((ev) => `
        <div class="event"><time>${ev.created_at.replace("T", " ")}</time>${ev.detail}</div>
      `).join("")}
    </div>
    <div class="actions">
      <button onclick="setStatus(${c.id}, 'in_progress')">▶️ เริ่มดำเนินการ</button>
      <button onclick="setStatus(${c.id}, 'resolved')">✅ ปิดเคส</button>
    </div>`;
  dashMap.setView([c.lat, c.lng], 15);
}

async function setStatus(id, status) {
  await fetch(`/api/cases/${id}/status`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ status }),
  });
  loadDashboard();
  openCase(id);
}

// ---------- Analytics tab ----------
async function loadAnalytics() {
  const a = await (await fetch("/api/analytics")).json();
  document.getElementById("analytics-totals").innerHTML = `
    <div class="stat"><div class="num">${a.totals.cases ?? 0}</div><div class="label">เคสทั้งหมด</div></div>
    <div class="stat"><div class="num">${a.totals.reports ?? 0}</div><div class="label">รายงานจากประชาชน</div></div>
    <div class="stat"><div class="num">${a.totals.impacted ?? 0}</div><div class="label">ผู้ได้รับผลกระทบรวม</div></div>`;

  const max = Math.max(...a.by_category.map((c) => c.count), 1);
  document.getElementById("chart-category").innerHTML = a.by_category.map((c) => `
    <div class="bar-row">
      <span class="name">${c.category_th}</span>
      <div class="bar" style="width:${(c.count / max) * 240}px"></div>
      <span class="n">${c.count}</span>
    </div>`).join("");

  document.getElementById("top-risk").innerHTML = a.top_risk.map((c) => `
    <div class="case-card" onclick="document.querySelector('[data-tab=dashboard]').click(); setTimeout(()=>openCase(${c.id}),300)">
      <div class="row">
        <span class="title">#${c.id} ${c.category_th}</span>
        <span class="badge ${riskClass(c.risk_level)}">Risk ${c.risk_score}</span>
      </div>
    </div>`).join("") || "<p>ไม่มีเคสค้าง 🎉</p>";
}

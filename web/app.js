'use strict';

const $ = (s) => document.querySelector(s);
const $$ = (s) => Array.from(document.querySelectorAll(s));
const esc = (s) => (s == null ? '' : String(s).replace(/[&<>"]/g,
  (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c])));

async function api(path, body) {
  const opt = body
    ? { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }
    : {};
  const r = await fetch(path, opt);
  const d = await r.json().catch(() => ({ ok: false, loi: 'phản hồi không hợp lệ' }));
  if (!d.ok && d.loi) throw new Error(d.loi);
  return d;
}

function bao(msg, kind) {
  const el = $('#thongBao');
  el.className = 'notice ' + (kind || '');
  el.textContent = msg;
  el.classList.toggle('hidden', !msg);
}

/* ================= tabs ================= */
$$('.tab').forEach((b) => b.addEventListener('click', () => {
  $$('.tab').forEach((x) => x.classList.remove('on'));
  $$('.panel').forEach((x) => x.classList.remove('on'));
  b.classList.add('on');
  $('#tab-' + b.dataset.tab).classList.add('on');
  if (b.dataset.tab === 'kho') napKho();
  if (b.dataset.tab === 'cai') napCaiDat();
}));

/* ================= tìm truyện ================= */
async function napNguon() {
  try {
    const d = await api('/api/sources');
    const sel = $('#oNguon');
    sel.innerHTML = '<option value="">Tất cả nguồn tìm được</option>' +
      d.nguon.filter((s) => s.can_search)
        .map((s) => `<option value="${esc(s.id)}">${esc(s.name)}</option>`).join('');
    $('#dsNguon').innerHTML = d.nguon.map((s) => `
      <div class="src"><b>${esc(s.name)}</b>
        <span class="d">${s.can_search ? 'tìm kiếm ✓' : 'chỉ nhận link'} ·
        ${esc(s.domains.join(', ') || 'mọi trang khác')}</span></div>`).join('');
  } catch (e) { bao('Không nạp được danh sách nguồn: ' + e.message, 'err'); }
}

async function tim() {
  const kw = $('#oTuKhoa').value.trim();
  if (!kw) return;
  if (/^https?:\/\//i.test(kw)) return moTruyen(kw);
  bao('Đang tìm…', 'info');
  $('#ketQua').innerHTML = '';
  try {
    const d = await api('/api/search?q=' + encodeURIComponent(kw) +
      '&source=' + encodeURIComponent($('#oNguon').value));
    veKetQua(d.ket_qua);
    bao(d.ket_qua.length ? '' : 'Không tìm thấy truyện nào khớp từ khoá này.',
      d.ket_qua.length ? '' : 'info');
    if (d.loi && d.loi.length) bao(d.loi.join('\n'), 'err');
  } catch (e) { bao('Lỗi tìm kiếm: ' + e.message, 'err'); }
}

function veKetQua(list) {
  $('#ketQua').innerHTML = list.map((b) => `
    <div class="card-book" data-url="${esc(b.url)}">
      <img loading="lazy" src="${esc(b.cover)}" alt="" onerror="this.style.visibility='hidden'">
      <div>
        <div class="t">${esc(b.title)}</div>
        ${b.author ? `<div class="a">${esc(b.author)}</div>` : ''}
        ${b.latest ? `<div class="s">${esc(b.latest)}</div>` : ''}
      </div>
    </div>`).join('');
  $$('#ketQua .card-book').forEach((c) =>
    c.addEventListener('click', () => moTruyen(c.dataset.url)));
}

let truyenHienTai = null;

async function moTruyen(url) {
  bao('Đang đọc trang truyện và lấy danh sách chương… (truyện dài có thể mất một lúc)', 'info');
  $('#chiTiet').classList.add('hidden');
  try {
    const d = await api('/api/book?url=' + encodeURIComponent(url));
    truyenHienTai = d.truyen;
    bao(d.canh_bao || '', d.canh_bao ? 'err' : '');
    veChiTiet(d.truyen);
  } catch (e) { bao('Không đọc được trang này: ' + e.message, 'err'); }
}

function veChiTiet(b) {
  $('#dBia').src = b.cover || '';
  $('#dBia').style.visibility = b.cover ? 'visible' : 'hidden';
  $('#dTen').textContent = b.title;
  $('#dTacGia').textContent = b.author ? 'Tác giả: ' + b.author : '';
  $('#dTheLoai').innerHTML = (b.genres || []).map((g) => `<span>${esc(g)}</span>`).join('');
  $('#dTrangThai').textContent = b.status ? 'Trạng thái: ' + b.status : '';
  $('#dSoChuong').textContent = b.chapters.length + ' chương';
  $('#dMoTa').textContent = b.description || '';
  $('#dMoTaBox').classList.toggle('hidden', !b.description);
  $('#oTu').value = 1;
  $('#oTu').max = b.chapters.length;
  $('#oDen').value = b.chapters.length;
  $('#oDen').max = b.chapters.length;
  $('#chiTiet').classList.remove('hidden');
  $('#chiTiet').scrollIntoView({ behavior: 'smooth', block: 'start' });
}

$('#btTim').addEventListener('click', tim);
$('#oTuKhoa').addEventListener('keydown', (e) => { if (e.key === 'Enter') tim(); });
$('#oTuKhoa').addEventListener('search', tim);   // Enter trong ô type=search
$('#btDong').addEventListener('click', () => $('#chiTiet').classList.add('hidden'));
$('#btTatCa').addEventListener('click', () => {
  if (!truyenHienTai) return;
  $('#oTu').value = 1; $('#oDen').value = truyenHienTai.chapters.length;
});
$('#btMoiNhat').addEventListener('click', () => {
  if (!truyenHienTai) return;
  const n = truyenHienTai.chapters.length;
  $('#oTu').value = Math.max(1, n - 99); $('#oDen').value = n;
});

$('#btTai').addEventListener('click', async () => {
  if (!truyenHienTai) return;
  const dinhDang = [];
  if ($('#fEpub').checked) dinhDang.push('epub');
  if ($('#fTxt').checked) dinhDang.push('txt');
  if (!dinhDang.length) return bao('Chọn ít nhất một định dạng xuất.', 'err');
  $('#btTai').disabled = true;
  try {
    await api('/api/download', {
      url: truyenHienTai.url,
      tu: Number($('#oTu').value) || 1,
      den: Number($('#oDen').value) || truyenHienTai.chapters.length,
      dinh_dang: dinhDang,
    });
    $$('.tab').find((t) => t.dataset.tab === 'tai').click();
    napViec();
  } catch (e) { bao('Không tạo được lượt tải: ' + e.message, 'err'); }
  $('#btTai').disabled = false;
});

/* ================= hàng đợi ================= */
const NHAN = { 'dang cho': '', 'dang tai': 'run', 'dang xuat': 'run', xong: 'done', loi: 'err', 'da huy': '' };
const CHU = {
  'dang cho': 'đang chờ', 'dang tai': 'đang tải', 'dang xuat': 'đang xuất file',
  xong: 'xong', loi: 'lỗi', 'da huy': 'đã huỷ',
};

async function napViec() {
  let d;
  try { d = await api('/api/jobs'); } catch { return; }
  const chay = d.viec.filter((j) => j.status === 'dang tai' || j.status === 'dang xuat' || j.status === 'dang cho').length;
  const pill = $('#soViec');
  pill.textContent = chay;
  pill.classList.toggle('hidden', !chay);

  $('#dsViec').innerHTML = d.viec.length ? d.viec.map((j) => `
    <div class="job">
      <div class="head">
        <div><div class="name">${esc(j.title)}</div>
          <div class="info">${esc(j.author || '')}</div></div>
        <span class="st ${NHAN[j.status] || ''}">${CHU[j.status] || j.status}</span>
      </div>
      <div class="bar"><i style="width:${j.percent}%"></i></div>
      <div class="info">
        <span>${j.done}/${j.total} chương · ${j.percent}%${j.cached ? ` · ${j.cached} chương có sẵn` : ''}</span>
        <span>${j.failed_count ? `<b style="color:var(--err)">${j.failed_count} chương lỗi</b>` : ''}</span>
      </div>
      ${j.message ? `<div class="info" style="margin-top:.35rem">${esc(j.message)}</div>` : ''}
      ${j.files && j.files.length ? `<div class="files">${j.files.map(esc).join('<br>')}</div>` : ''}
      <div class="acts">
        ${['dang tai', 'dang cho', 'dang xuat'].includes(j.status)
      ? `<button data-huy="${j.id}">Dừng</button>` : ''}
        ${j.folder ? `<button data-mo="${esc(j.folder)}">Mở thư mục</button>` : ''}
      </div>
    </div>`).join('') : '<div class="empty">Chưa có lượt tải nào.</div>';

  $$('[data-huy]').forEach((b) => b.addEventListener('click', async () => {
    await api('/api/job/cancel', { id: b.dataset.huy }); napViec();
  }));
  $$('[data-mo]').forEach((b) => b.addEventListener('click', () =>
    api('/api/open', { duong_dan: b.dataset.mo }).catch(() => { })));
}

$('#btXoaXong').addEventListener('click', async () => {
  await api('/api/job/clear', {}); napViec();
});
setInterval(napViec, 1200);

/* ================= thư viện ================= */
async function napKho() {
  try {
    const d = await api('/api/library');
    $('#dsKho').innerHTML = d.thu_vien.length ? d.thu_vien.map((b) => `
      <div class="card-book" data-mo="${esc(b.folder)}">
        <img loading="lazy" src="${esc(b.cover)}" alt="" onerror="this.style.visibility='hidden'">
        <div>
          <div class="t">${esc(b.title)}</div>
          <div class="a">${esc(b.author || '')}</div>
          <div class="s">${b.chapters} chương · ${(b.files || []).length} file</div>
        </div>
      </div>`).join('') : '<div class="empty">Chưa tải truyện nào.</div>';
    $$('#dsKho [data-mo]').forEach((c) => c.addEventListener('click', () =>
      api('/api/open', { duong_dan: c.dataset.mo }).catch(() => { })));
  } catch (e) { $('#dsKho').innerHTML = '<div class="empty">Lỗi: ' + esc(e.message) + '</div>'; }
}

$('#btMoThuMuc').addEventListener('click', () => api('/api/open', {}).catch(() => { }));

/* ================= cài đặt ================= */
async function napCaiDat() {
  try {
    const d = await api('/api/settings');
    const c = d.cai_dat, f = d.bo_loc;
    $('#sThuMuc').value = c.output_dir;
    $('#sLuong').value = c.threads;
    $('#sNghi').value = c.delay;
    $('#sThuLai').value = c.retries;
    $('#sTach').value = c.split_every;
    $('#sProxy').value = c.proxy || '';
    $('#sTuLoc').checked = !!c.auto_clean;
    $('#fRemove').value = (f.remove || []).join('\n');
    $('#fDrop').value = (f.drop_line || []).join('\n');
    $('#fNames').value = Object.entries(f.names || {}).map(([k, v]) => `${k} = ${v}`).join('\n');
  } catch (e) { console.error(e); }
}

$('#btLuu').addEventListener('click', async () => {
  const names = {};
  $('#fNames').value.split('\n').forEach((line) => {
    const i = line.indexOf('=');
    if (i > 0) names[line.slice(0, i).trim()] = line.slice(i + 1).trim();
  });
  const dong = (id) => $(id).value.split('\n').map((s) => s.trim()).filter(Boolean);
  try {
    await api('/api/settings', {
      cai_dat: {
        output_dir: $('#sThuMuc').value.trim(),
        threads: Number($('#sLuong').value),
        delay: Number($('#sNghi').value),
        retries: Number($('#sThuLai').value),
        split_every: Number($('#sTach').value),
        proxy: $('#sProxy').value.trim(),
        auto_clean: $('#sTuLoc').checked,
      },
      bo_loc: { remove: dong('#fRemove'), drop_line: dong('#fDrop'), regex: [], names },
    });
    const ok = $('#luuXong');
    ok.classList.remove('hidden');
    setTimeout(() => ok.classList.add('hidden'), 1800);
  } catch (e) { alert('Không lưu được: ' + e.message); }
});

$('#btNapLai').addEventListener('click', async () => {
  await api('/api/reload', {});
  napNguon();
});

/* ================= khởi động ================= */
napNguon();
napViec();

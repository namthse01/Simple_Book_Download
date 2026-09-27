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

/* ================= hộp thoại =================
   Tự vẽ thay vì dùng confirm()/alert() của trình duyệt: khi chạy trong cửa sổ
   app (WebView2) các hộp thoại đó có thể bị chặn, bấm Xoá sẽ không hỏi gì. */
let htTraLoi = null;

function moHopThoai(noiDung, chiBao) {
  $('#htNoiDung').textContent = noiDung;
  $('#htHuy').classList.toggle('hidden', !!chiBao);
  $('#htOk').textContent = chiBao ? 'Đóng' : 'Đồng ý';
  $('#hopThoai').classList.remove('hidden');
  $('#htOk').focus();
  return new Promise((res) => { htTraLoi = res; });
}

function dongHopThoai(ok) {
  $('#hopThoai').classList.add('hidden');
  if (htTraLoi) { htTraLoi(ok); htTraLoi = null; }
}

const hoi = (t) => moHopThoai(t, false);      // hỏi Đồng ý / Huỷ
const nhac = (t) => moHopThoai(t, true);      // chỉ báo một dòng

$('#htOk').addEventListener('click', () => dongHopThoai(true));
$('#htHuy').addEventListener('click', () => dongHopThoai(false));
$('#hopThoai').addEventListener('click', (e) => {
  if (e.target.id === 'hopThoai') dongHopThoai(false);
});

/* ================= tabs ================= */
$$('.tab').forEach((b) => b.addEventListener('click', () => {
  $$('.tab').forEach((x) => x.classList.remove('on'));
  $$('.panel').forEach((x) => x.classList.remove('on'));
  b.classList.add('on');
  $('#tab-' + b.dataset.tab).classList.add('on');
  if (b.dataset.tab === 'kho') napKho();
  if (b.dataset.tab === 'cai') napCaiDat();
  if (b.dataset.tab === 'bao') moTabBao();
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

/* chữ cái đầu của tên truyện — hiện to mờ trên bìa khi không có ảnh */
function chuDau(ten) {
  return String(ten || '?').trim().split(/\s+/).slice(0, 2)
    .map((t) => t.charAt(0).toUpperCase()).join('');
}

function veKetQua(list) {
  $('#ketQua').innerHTML = list.map((b) => `
    <div class="pcard" data-url="${esc(b.url)}" title="${esc(b.title)}">
      <div class="pcover">
        <span class="pchu">${esc(chuDau(b.title))}</span>
        ${b.cover ? `<img loading="lazy" referrerpolicy="no-referrer"
          src="${esc(b.cover)}" alt="" onerror="this.remove()">` : ''}
      </div>
      <div class="pinfo">
        <div class="t">${esc(b.title)}</div>
        ${b.author ? `<div class="a">${esc(b.author)}</div>` : ''}
        ${b.latest ? `<div class="s">${esc(b.latest)}</div>` : ''}
      </div>
    </div>`).join('');
  $$('#ketQua .pcard').forEach((c) =>
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

  // Phai gioi han trong #dsViec: ham nay chay lai moi 1,2 giay, neu chon toan
  // trang thi cac nut ben tab Thu vien se bi gan them mot lan nghe moi moi luot.
  $$('#dsViec [data-huy]').forEach((b) => b.addEventListener('click', async () => {
    await api('/api/job/cancel', { id: b.dataset.huy }); napViec();
  }));
  $$('#dsViec [data-mo]').forEach((b) => b.addEventListener('click', () =>
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
    // đang đọc dở cuốn nào thì đưa nút "Đọc tiếp" lên đầu thư viện
    let ganNhat = '';
    try { ganNhat = localStorage.getItem('doc:gan-nhat') || ''; } catch (e) { /**/ }
    const gn = d.thu_vien.find((x) => x.url === ganNhat);
    $('#khoDocTiep').innerHTML = gn
      ? `<button class="primary big" id="btDocTiep">▶ Đọc tiếp: ${esc(gn.title)}</button>` : '';
    if (gn) $('#btDocTiep').addEventListener('click', () => moDoc(gn.url));
    $('#dsKho').innerHTML = d.thu_vien.length ? d.thu_vien.map((b) => {
      let pct = 0;
      try {
        const i = Number(localStorage.getItem('doc:' + b.url)) || 0;
        pct = i && b.chapters ? Math.min(100, Math.round(i * 100 / b.chapters)) : 0;
      } catch (e) { /**/ }
      return `
      <div class="pcard" data-sach="${esc(b.url)}" title="${esc(b.title)}">
        <div class="pcover">
          <span class="pchu">${esc(chuDau(b.title))}</span>
          ${b.cover ? `<img loading="lazy" src="${esc(b.cover)}" alt="" onerror="this.remove()">` : ''}
          ${pct ? `<div class="ptien"><i style="width:${pct}%"></i></div>` : ''}
          <div class="pacts">
            <button data-doc="${esc(b.url)}" title="Mở đọc ngay chỗ đang dở">▶ Đọc</button>
            <button class="ptham" data-tham="${esc(b.url)}" data-ten="${esc(b.title)}"
              title="Thâm nhập — nhập vai vào thế giới truyện">⚔</button>
          </div>
        </div>
        <div class="pinfo">
          <div class="t">${esc(b.title)}</div>
          <div class="a">${esc(b.author || '')}</div>
          <div class="s">${b.chapters} chương${pct ? ` · đã đọc ${pct}%` : ''}</div>
        </div>
      </div>`;
    }).join('') : '<div class="empty">Chưa tải truyện nào — sang tab Tìm truyện, hoặc bấm ＋ Nhập tài liệu.</div>';
    // bấm thẻ -> màn truyện (chọn chương, cập nhật, thư mục, xoá đều ở đó);
    // hai nút trên bìa đi thẳng: Đọc tiếp / Thâm nhập thế giới
    $$('#dsKho .pcard').forEach((c) => c.addEventListener('click', (e) => {
      if (e.target.closest('button')) return;
      moManTruyen(c.dataset.sach);
    }));
    $$('#dsKho [data-doc]').forEach((b) => b.addEventListener('click', (e) => {
      e.stopPropagation();
      moDoc(b.dataset.doc);
    }));
    $$('#dsKho [data-tham]').forEach((b) => b.addEventListener('click', (e) => {
      e.stopPropagation();
      moTheGioi(b.dataset.tham, b.dataset.ten);
    }));
  } catch (e) { $('#dsKho').innerHTML = '<div class="empty">Lỗi: ' + esc(e.message) + '</div>'; }
}

$('#btMoThuMuc').addEventListener('click', () => api('/api/open', {}).catch(() => { }));

/* ================= nhập tài liệu (EPUB/TXT có sẵn trên máy) ================= */
let NHAP = [];   // [{name, file}]

$('#btNhap').addEventListener('click', () => $('#oFileNhap').click());
$('#nhThem').addEventListener('click', () => $('#oFileNhap').click());
$('#oFileNhap').addEventListener('change', () => {
  themFileNhap($('#oFileNhap').files);
  $('#oFileNhap').value = '';
});

// kéo thả file vào bất kỳ đâu trong cửa sổ
document.addEventListener('dragover', (e) => {
  if (e.dataTransfer && Array.from(e.dataTransfer.types).includes('Files')) e.preventDefault();
});
document.addEventListener('drop', (e) => {
  if (!e.dataTransfer || !e.dataTransfer.files.length) return;
  e.preventDefault();
  themFileNhap(e.dataTransfer.files);
});

function themFileNhap(list) {
  const ok = Array.from(list).filter((f) => /\.(epub|txt|docx|pdf|x?html?|md|markdown)$/i.test(f.name));
  if (!ok.length) { nhac('Chỉ nhận file EPUB, TXT, DOCX, PDF, HTML hoặc Markdown.'); return; }
  // sắp lô mới theo tên (phan1, phan2, … đúng thứ tự số) rồi nối vào cuối
  ok.sort((a, b) => a.name.localeCompare(b.name, 'vi', { numeric: true }));
  NHAP = NHAP.concat(ok.filter((f) => !NHAP.some((x) => x.name === f.name))
    .map((f) => ({ name: f.name, file: f })));
  $('#nhBao').textContent = '';
  veNhap();
  $('#manNhap').classList.remove('hidden');
}

function veNhap() {
  const kb = (n) => (n > 1048576 ? (n / 1048576).toFixed(1) + ' MB' : Math.ceil(n / 1024) + ' KB');
  $('#nhDs').innerHTML = NHAP.length ? NHAP.map((x, i) => `
    <div class="nhap-f">
      <span class="n">${esc(x.name)}</span><span class="s">${kb(x.file.size)}</span>
      <button class="ghost" data-len="${i}" title="Đưa lên trên" ${i ? '' : 'disabled'}>↑</button>
      <button class="ghost" data-bo="${i}" title="Bỏ file này">✕</button>
    </div>`).join('') : '<div class="empty">Chưa chọn file nào.</div>';
  $$('#nhDs [data-len]').forEach((b) => b.addEventListener('click', () => {
    const i = Number(b.dataset.len);
    [NHAP[i - 1], NHAP[i]] = [NHAP[i], NHAP[i - 1]];
    veNhap();
  }));
  $$('#nhDs [data-bo]').forEach((b) => b.addEventListener('click', () => {
    NHAP.splice(Number(b.dataset.bo), 1);
    veNhap();
  }));
  $('#nhGopKhung').classList.toggle('hidden', NHAP.length < 2);
  // tên sách/tác giả gõ tay chỉ có nghĩa khi 1 file, hoặc khi gộp thành 1 cuốn
  const suaDuoc = NHAP.length === 1 || (NHAP.length > 1 && $('#nhGop').checked);
  $('#nhTen').disabled = !suaDuoc;
  $('#nhTacGia').disabled = !suaDuoc;
  // danh sách file / thứ tự / kiểu gộp đổi rồi thì mục lục xem thử cũ hết đúng
  $('#nhThu').classList.add('hidden');
  $('#nhThu').innerHTML = '';
}

$('#nhGop').addEventListener('change', veNhap);
$('#nhHuy').addEventListener('click', () => {
  NHAP = [];
  $('#manNhap').classList.add('hidden');
});

const docB64 = (file) => new Promise((res, rej) => {
  const r = new FileReader();
  r.onload = () => res(String(r.result).split(',')[1] || '');
  r.onerror = () => rej(new Error('không đọc được ' + file.name));
  r.readAsDataURL(file);
});

async function guiNhap(thu) {
  // đọc file thành base64 rồi gửi; thu=true chỉ tách chương để xem trước
  $('#nhBao').textContent = 'Đang đọc file…';
  const files = [];
  for (const x of NHAP) files.push({ name: x.name, b64: await docB64(x.file) });
  $('#nhBao').textContent = thu
    ? 'Đang tách chương thử… (file lớn có thể mất một lúc)'
    : 'Đang tách chương và đóng gói… (file lớn có thể mất một lúc)';
  const dinhDang = [];
  if ($('#nhEpub').checked) dinhDang.push('epub');
  if ($('#nhTxt').checked) dinhDang.push('txt');
  return api('/api/import', {
    files,
    thu: !!thu,
    gop: NHAP.length > 1 && $('#nhGop').checked,
    ten: $('#nhTen').value.trim(),
    tac_gia: $('#nhTacGia').value.trim(),
    dinh_dang: dinhDang,
  });
}

$('#nhXemThu').addEventListener('click', async () => {
  if (!NHAP.length) return;
  const nut = $('#nhXemThu');
  nut.disabled = true;
  try {
    const d = await guiNhap(true);
    $('#nhBao').textContent = '';
    $('#nhThu').innerHTML = d.sach.map((s) => `
      <div class="thu-sach">
        <b>${esc(s.title)}</b>${s.author ? ' — ' + esc(s.author) : ''}
        <span class="s">· ${s.chapters} chương</span>
        <ol>${s.muc_luc.map((t) => `<li>${esc(t)}</li>`).join('')}${
        s.chapters > s.muc_luc.length ? '<li>… còn nữa</li>' : ''}</ol>
      </div>`).join('')
      + (d.loi && d.loi.length
        ? `<div class="thu-loi">${d.loi.map(esc).join('<br>')}</div>` : '');
    $('#nhThu').classList.remove('hidden');
  } catch (e) {
    $('#nhBao').textContent = 'Không xem thử được: ' + e.message;
  }
  nut.disabled = false;
});

$('#nhOk').addEventListener('click', async () => {
  if (!NHAP.length) return;
  if (!$('#nhEpub').checked && !$('#nhTxt').checked) {
    nhac('Chọn ít nhất một định dạng xuất.');
    return;
  }
  const nut = $('#nhOk');
  nut.disabled = true;
  try {
    const d = await guiNhap(false);
    NHAP = [];
    $('#manNhap').classList.add('hidden');
    $('#nhTen').value = '';
    $('#nhTacGia').value = '';
    napKho();
    if (d.loi && d.loi.length) await nhac('Có file không nhập được:\n' + d.loi.join('\n'));
    else if (d.sach.length) await nhac('Đã nhập ' + d.sach.length + ' cuốn vào thư viện.');
  } catch (e) {
    $('#nhBao').textContent = 'Không nhập được: ' + e.message;
  }
  nut.disabled = false;
});

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
    $('#sLan').checked = !!c.lan;
    napLan();
    $('#fRemove').value = (f.remove || []).join('\n');
    $('#fDrop').value = (f.drop_line || []).join('\n');
    $('#fNames').value = Object.entries(f.names || {}).map(([k, v]) => `${k} = ${v}`).join('\n');
    const ai = c.ai || {};
    $('#aiUrl').value = ai.base_url || '';
    $('#aiKey').value = ai.api_key || '';
    $('#aiModel').value = ai.model || '';
    $('#aiNhiet').value = ai.temperature != null ? ai.temperature : 0.8;
    $('#aiTimeout').value = ai.timeout || 600;
    $('#aiChunk').value = ai.chunk_chars || 20000;
    $('#aiCtx').value = ai.num_ctx || 24576;
    $('#aiTrauChuot').checked = !!ai.trau_chuot;
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
        lan: $('#sLan').checked,
        ai: {
          base_url: $('#aiUrl').value.trim(),
          api_key: $('#aiKey').value.trim(),
          model: $('#aiModel').value.trim(),
          temperature: Number($('#aiNhiet').value) || 0.8,
          max_tokens: 3000,
          timeout: Number($('#aiTimeout').value) || 600,
          chunk_chars: Number($('#aiChunk').value) || 20000,
          num_ctx: Number($('#aiCtx').value) || 24576,
          trau_chuot: $('#aiTrauChuot').checked,
        },
      },
      bo_loc: { remove: dong('#fRemove'), drop_line: dong('#fDrop'), regex: [], names },
    });
    const ok = $('#luuXong');
    ok.classList.remove('hidden');
    setTimeout(() => ok.classList.add('hidden'), 1800);
    napLan();
  } catch (e) { nhac('Không lưu được: ' + e.message); }
});

async function napLan() {
  try {
    const d = await api('/api/lan-info');
    $('#lanKhung').classList.toggle('hidden', !d.mo_rong);
    const canKhoiDongLai = d.lan && !d.mo_rong;
    $('#lanBao').classList.toggle('hidden', !canKhoiDongLai);
    if (canKhoiDongLai) {
      $('#lanBao').textContent =
        'Đã bật, nhưng app đang chạy theo kiểu cũ — tắt mở lại app là điện thoại vào được.';
    }
    if (d.mo_rong) {
      $('#lanQr').innerHTML = d.qr || '';
      $('#lanUrl').textContent = d.url;
    }
  } catch (e) { /* không chặn màn cài đặt chỉ vì thiếu thông tin mạng */ }
}

$('#btNapLai').addEventListener('click', async () => {
  await api('/api/reload', {});
  napNguon();
});

/* ================= khởi động ================= */
napNguon();
napViec();

/* ================= xoá truyện ================= */
async function xoaTruyen(url, ten) {
  const ok = await hoi(`Xoá "${ten}" khỏi thư viện và xoá luôn thư mục file đã tải?\n\n`
    + 'Không hoàn tác được — muốn đọc lại thì phải tải lại từ đầu.');
  if (!ok) return;
  try {
    const d = await api('/api/library/delete', { url });
    if (d.loi) await nhac('Đã xoá khỏi thư viện, nhưng ' + d.loi);
    try { localStorage.removeItem('doc:' + url); } catch (e) { /* bỏ qua */ }
    napKho();
  } catch (e) { nhac('Không xoá được: ' + e.message); }
}

/* ================= trình đọc ================= */
const DOC = { url: '', ten: '', chuong: [], i: 0 };

const nhoViTri = (url, idx) => { try { localStorage.setItem('doc:' + url, String(idx)); } catch (e) { /**/ } };
const doiViTri = (url) => { try { return Number(localStorage.getItem('doc:' + url)) || 0; } catch (e) { return 0; } };

async function moDoc(url, batDau) {
  try {
    const d = await api('/api/read/list?url=' + encodeURIComponent(url));
    DOC.url = url;
    DOC.ten = d.truyen.title;
    DOC.chuong = d.chuong;
    $('#rTenTruyen').textContent = DOC.ten;
    veMucLuc();
    kieuDoc();
    $('#rBang').classList.add('hidden');
    $('#docTruyen').classList.remove('hidden');
    try { localStorage.setItem('doc:gan-nhat', url); } catch (e) { /**/ }
    const moc = batDau != null ? batDau : doiViTri(url);
    const vt = DOC.chuong.findIndex((c) => c.index === moc);
    await doChuong(vt >= 0 ? vt : 0);
  } catch (e) {
    nhac('Không mở được truyện này: ' + e.message
      + '\n\nCó thể thư mục chương đã bị xoá — thử tải lại truyện.');
  }
}

function veMucLuc() {
  $('#rDsChuong').innerHTML = DOC.chuong
    .map((c, i) => `<button data-i="${i}">${esc(c.title)}</button>`).join('');
  $$('#rDsChuong button').forEach((b) =>
    b.addEventListener('click', () => doChuong(Number(b.dataset.i))));
}

async function doChuong(i) {
  if (i < 0 || i >= DOC.chuong.length) return;
  const ch = DOC.chuong[i];
  const box = $('#rNoiDung');
  box.innerHTML = '<div class="khung"><p class="het">Đang mở…</p></div>';
  try {
    const d = await api('/api/read/chapter?url=' + encodeURIComponent(DOC.url)
      + '&index=' + ch.index);
    DOC.i = i;
    const cuoi = i === DOC.chuong.length - 1;
    $('#rTenChuong').textContent = d.chuong.title;
    box.innerHTML = '<div class="khung"><h2>' + esc(d.chuong.title) + '</h2>'
      + d.chuong.lines.map((l) => '<p>' + esc(l) + '</p>').join('')
      + (cuoi ? '<p class="het">— Hết phần đã tải về —</p>'
        : '<button class="het-nut">Chương sau →</button>')
      + '</div>';
    const nutSau = box.querySelector('.het-nut');
    if (nutSau) nutSau.addEventListener('click', () => doChuong(i + 1));
    // đọc dở chương này lần trước thì trả lại đúng chỗ đang cuộn
    let cuon = 0;
    try {
      const [ci, ty] = (localStorage.getItem('doc:cuon:' + DOC.url) || '').split(':');
      if (Number(ci) === ch.index) cuon = Number(ty) || 0;
    } catch (e) { /**/ }
    box.scrollTop = cuon > 0.01 && cuon < 0.99
      ? cuon * (box.scrollHeight - box.clientHeight) : 0;
    capNhatPhanTram();
    $('#rTruoc').disabled = i === 0;
    $('#rSau').disabled = cuoi;
    $$('#rDsChuong button').forEach((b, k) => b.classList.toggle('on', k === i));
    const cur = $('#rDsChuong button.on');
    if (cur) cur.scrollIntoView({ block: 'nearest' });
    nhoViTri(DOC.url, ch.index);
  } catch (e) {
    box.innerHTML = '<div class="khung"><p class="het">Không đọc được chương này: '
      + esc(e.message) + '</p></div>';
  }
}

/* ---- nhớ chỗ cuộn + phần trăm đã đọc ---- */
function tyLeCuon() {
  const nd = $('#rNoiDung');
  const max = nd.scrollHeight - nd.clientHeight;
  return max > 5 ? Math.min(1, nd.scrollTop / max) : 1;
}

function capNhatPhanTram() {
  if (!DOC.chuong.length) return;
  $('#rViTri').textContent =
    `Chương ${DOC.i + 1}/${DOC.chuong.length} · ${Math.round(tyLeCuon() * 100)}%`;
}

let cuonHen = 0;
$('#rNoiDung').addEventListener('scroll', () => {
  capNhatPhanTram();
  clearTimeout(cuonHen);
  cuonHen = setTimeout(() => {
    if (!DOC.url || !DOC.chuong.length) return;
    try {
      localStorage.setItem('doc:cuon:' + DOC.url,
        DOC.chuong[DOC.i].index + ':' + tyLeCuon().toFixed(4));
    } catch (e) { /**/ }
  }, 300);
});

/* ---- kiểu đọc: cỡ chữ, phông, giãn dòng, bề ngang, nền ---- */
const KIEU_MAC_DINH = { co: 18, phong: 'sans', gian: '1.85', rong: '44', nen: 'toi' };

function docKieu() {
  const k = { ...KIEU_MAC_DINH };
  try {
    const luu = JSON.parse(localStorage.getItem('doc:kieu') || 'null');
    if (luu) return { ...k, ...luu };
    // chuyển cài đặt từ bản cũ (chỉ có cỡ chữ + nền giấy)
    k.co = Number(localStorage.getItem('doc:co')) || k.co;
    if (localStorage.getItem('doc:nen') === 'giay') k.nen = 'giay';
  } catch (e) { /* trình duyệt chặn localStorage thì dùng mặc định */ }
  return k;
}

function doiKieu(key, val) {
  const k = docKieu();
  k[key] = val;
  try { localStorage.setItem('doc:kieu', JSON.stringify(k)); } catch (e) { /**/ }
  kieuDoc();
}

function kieuDoc() {
  const k = docKieu();
  const nd = $('#rNoiDung');
  nd.style.setProperty('--co-chu', k.co + 'px');
  nd.style.setProperty('--gian-doc', k.gian);
  nd.style.setProperty('--rong-doc', k.rong + 'rem');
  nd.style.setProperty('--font-doc', k.phong === 'serif'
    ? "Georgia,'Times New Roman',serif"
    : "'Segoe UI',system-ui,-apple-system,sans-serif");
  $('#docTruyen').classList.toggle('giay', k.nen === 'giay');
  $('#docTruyen').classList.toggle('den', k.nen === 'den');
  $('#rCoChu').textContent = k.co;
  [['#rPhong', k.phong], ['#rGian', k.gian], ['#rRong', k.rong], ['#rNenOps', k.nen]]
    .forEach(([sel, val]) => $$(sel + ' button')
      .forEach((b) => b.classList.toggle('on', b.dataset.v === String(val))));
}

$('#rAa').addEventListener('click', () => $('#rBang').classList.toggle('hidden'));
$('#rNho').addEventListener('click', () => doiKieu('co', Math.max(13, docKieu().co - 1)));
$('#rTo').addEventListener('click', () => doiKieu('co', Math.min(34, docKieu().co + 1)));
[['#rPhong', 'phong'], ['#rGian', 'gian'], ['#rRong', 'rong'], ['#rNenOps', 'nen']]
  .forEach(([sel, key]) => $$(sel + ' button')
    .forEach((b) => b.addEventListener('click', () => doiKieu(key, b.dataset.v))));
// bấm vào phần chữ thì thu bảng chỉnh lại
$('#rNoiDung').addEventListener('click', () => $('#rBang').classList.add('hidden'));

$('#rDong').addEventListener('click', () => $('#docTruyen').classList.add('hidden'));
$('#rTruoc').addEventListener('click', () => doChuong(DOC.i - 1));
$('#rSau').addEventListener('click', () => doChuong(DOC.i + 1));
$('#rMucLuc').addEventListener('click', () => $('#rDsChuong').classList.toggle('hidden'));

document.addEventListener('keydown', (e) => {
  if ($('#docTruyen').classList.contains('hidden')) return;
  if (e.target.matches && e.target.matches('input, textarea, select')) return;
  if (e.key === 'ArrowLeft') doChuong(DOC.i - 1);
  else if (e.key === 'ArrowRight') doChuong(DOC.i + 1);
  else if (e.key === 'Escape') $('#docTruyen').classList.add('hidden');
});

/* ================= màn hình truyện (chọn chương) ================= */
const KHO = { url: '', ten: '', chuong: [], folder: '' };

async function moManTruyen(url) {
  const muc = (await api('/api/library')).thu_vien.find((x) => x.url === url);
  KHO.url = url;
  KHO.folder = muc ? muc.folder : '';
  // sách nhập từ máy không có nguồn web -> không có gì để "cập nhật chương mới"
  $('#mtCapNhat').classList.toggle('hidden', url.startsWith('local:'));
  try {
    const d = await api('/api/read/list?url=' + encodeURIComponent(url));
    KHO.ten = d.truyen.title;
    KHO.chuong = d.chuong;
    $('#mtTen').textContent = d.truyen.title;
    $('#mtTen2').textContent = d.truyen.title;
    $('#mtTacGia').textContent = d.truyen.author ? 'Tác giả: ' + d.truyen.author : '';
    $('#mtBia').src = d.truyen.cover || '';
    $('#mtBia').style.visibility = d.truyen.cover ? 'visible' : 'hidden';
    $('#mtSoChuong').textContent = d.chuong.length + ' chương đã tải về';
    $('#mtBao').textContent = '';
    $('#mtLoc').value = '';
    veDsChuong('');
    capNhatNutDocTiep();
    $('#manTruyen').classList.remove('hidden');
    // mở ra phải thấy bìa và nút Đọc trước, không nhảy thẳng xuống danh sách
    $('#manTruyen').querySelector('.sheet-body').scrollTop = 0;
  } catch (e) {
    nhac('Không mở được truyện này: ' + e.message
      + '\n\nCó thể thư mục chương đã bị xoá — thử tải lại truyện.');
  }
}

function capNhatNutDocTiep() {
  const cu = doiViTri(KHO.url);
  const c = KHO.chuong.find((x) => x.index === cu);
  $('#mtDocTiep').textContent = c ? 'Đọc tiếp: ' + c.title : 'Bắt đầu đọc';
}

function veDsChuong(loc) {
  const q = (loc || '').trim().toLowerCase();
  const ds = q ? KHO.chuong.filter((c) =>
    c.title.toLowerCase().includes(q) || String(c.index) === q) : KHO.chuong;
  const dangDoc = doiViTri(KHO.url);
  $('#mtDsChuong').innerHTML = ds.length
    ? ds.map((c) => `<button data-ch="${c.index}"${c.index === dangDoc ? ' class="dangDoc"' : ''}
        title="${esc(c.title)}">${esc(c.title)}</button>`).join('')
    : '<div class="empty">Không có chương nào khớp.</div>';
  $$('#mtDsChuong [data-ch]').forEach((b) => b.addEventListener('click',
    () => moDoc(KHO.url, Number(b.dataset.ch))));
}

$('#mtLoc').addEventListener('input', () => veDsChuong($('#mtLoc').value));
$('#mtDong').addEventListener('click', () => $('#manTruyen').classList.add('hidden'));
$('#mtDocDau').addEventListener('click', () => {
  if (KHO.chuong.length) moDoc(KHO.url, KHO.chuong[0].index);
});
$('#mtDocTiep').addEventListener('click', () => moDoc(KHO.url));
$('#mtThuMuc').addEventListener('click', () =>
  api('/api/open', { duong_dan: KHO.folder }).catch(() => { }));
$('#mtXoa').addEventListener('click', async () => {
  await xoaTruyen(KHO.url, KHO.ten);
  if (!(await api('/api/library')).thu_vien.some((x) => x.url === KHO.url)) {
    $('#manTruyen').classList.add('hidden');
  }
});

/* ================= thâm nhập thế giới ================= */
const TG = { url: '', ten: '', trangThai: '', hen: 0 };
const enc = encodeURIComponent;

const TEN_MUC = {
  tong_quan: 'Tổng quan thế giới',
  lich_su: 'Lịch sử: thời đại, chiến tranh, nguyên nhân – hậu quả',
  ban_do: 'Cấu trúc & bản đồ: quốc gia, khu vực, khoảng cách',
  the_gioi_song: 'Thời gian & môi trường: mùa, thời tiết, sinh thái',
  nhan_vat: 'Nhân vật & quy tắc sinh NPC',
  phe_phai: 'Phe phái & chính trị',
  van_hoa: 'Văn hoá & kinh tế',
  quy_luat: 'Quy luật thế giới: ma pháp, nhân quả, cái chết',
  gioi_han: 'Giới hạn & hệ thống sức mạnh',
  khu_vuc: 'Khu vực & sự kiện theo độ hiếm',
  bi_an: '🔒 Bí mật — xem sẽ spoil!',
};

function tgView(id) {
  ['tgChuaCo', 'tgDangXay', 'tgLoi', 'tgSanSang', 'tgTaoNV'].forEach((v) =>
    $('#' + v).classList.toggle('hidden', v !== id));
}

async function moTheGioi(url, ten) {
  TG.url = url;
  TG.ten = ten || '';
  $('#tgTen').textContent = TG.ten;
  $('#manTheGioi').classList.remove('hidden');
  tgView('');
  await tgNap();
}

async function tgNap() {
  let d;
  try { d = await api('/api/world/status?url=' + enc(TG.url)); }
  catch (e) {
    tgView('tgLoi');
    $('#tgLoiMsg').textContent = e.message;
    return;
  }
  TG.trangThai = d.status || '';
  $('#tgTinhTrang').textContent = TG.trangThai ? 'Truyện: ' + TG.trangThai : '';

  if (d.build && d.build.status === 'dang chay') {
    veXay(d.build);
    batDauHen();
    return;
  }
  if (d.world && (d.sections_done || []).length >= (d.sections_total || 7)) {
    veSanSang(d);
    return;
  }
  if (d.build && d.build.status === 'loi') {
    tgView('tgLoi');
    $('#tgLoiMsg').textContent = 'Kiến tạo thế giới bị lỗi:\n\n' + d.build.message;
    return;
  }

  // chưa có thế giới (hoặc mới xong một phần do dừng giữa chừng)
  tgView('tgChuaCo');
  const daPhan = d.world || (d.build && d.build.status === 'da huy');
  $('#tgXayNut').textContent = daPhan ? 'Khởi tạo tiếp (giữ phần đã phân tích)' : 'Khởi tạo thế giới';
  const cb = $('#tgCanhBao');
  const hoanThanh = /hoàn thành|hoàn tất|full|đã đủ/i.test(TG.trangThai);
  if (TG.trangThai && !hoanThanh) {
    cb.className = 'notice err';
    cb.textContent = '⚠ Truyện này CHƯA hoàn thành (' + TG.trangThai + '). Thế giới dựng ra '
      + 'sẽ thiếu phần kết và các bí ẩn chưa được tác giả giải — vẫn chơi được, nhưng '
      + 'truyện đã hoàn thành sẽ cho thế giới trọn vẹn hơn.';
    cb.classList.remove('hidden');
  } else if (!TG.trangThai) {
    cb.className = 'notice';
    cb.textContent = 'Không rõ truyện này đã hoàn thành chưa (sách nhập từ máy không có thông tin '
      + 'trạng thái). Nếu truyện còn dang dở, thế giới sẽ thiếu phần kết — cân nhắc trước khi vào.';
    cb.classList.remove('hidden');
  } else cb.classList.add('hidden');
  $('#tgAiHint').textContent = 'AI dùng máy chủ đã khai trong Cài đặt › Nhập vai AI. '
    + 'Truyện dài + chế độ Đầy đủ có thể chạy hàng giờ với model trên máy — cứ để chạy nền, dừng lúc nào cũng được.';
}

function veXay(b) {
  tgView('tgDangXay');
  $('#tgBuoc').innerHTML = b.stages.map((s, i) => `
    <li class="${i < b.stage_index ? 'xong' : i === b.stage_index ? 'dang' : ''}">${esc(s.ten)}${
    i === b.stage_index && b.total > 1 ? ` — ${b.done}/${b.total}` : ''}</li>`).join('');
  $('#tgBar').style.width = (b.total ? Math.round(b.done * 100 / b.total) : 0) + '%';
  $('#tgMsg').textContent = b.message || '';
}

function batDauHen() {
  if (!TG.hen) TG.hen = setInterval(tgTick, 2000);
}

function dungHen() {
  clearInterval(TG.hen);
  TG.hen = 0;
}

async function tgTick() {
  if ($('#manTheGioi').classList.contains('hidden')) { dungHen(); return; }
  try {
    const d = await api('/api/world/status?url=' + enc(TG.url));
    if (d.build && d.build.status === 'dang chay') { veXay(d.build); return; }
    dungHen();
    tgNap();
  } catch (e) { /* mạng chớp nháy thì lần tới hỏi lại */ }
}

$('#tgDong').addEventListener('click', () => {
  $('#manTheGioi').classList.add('hidden');
  dungHen();
});

$('#tgXayNut').addEventListener('click', async () => {
  const cheDo = (document.querySelector('input[name=tgCheDo]:checked') || {}).value || 'day_du';
  $('#tgXayNut').disabled = true;
  try {
    await api('/api/world/build', { url: TG.url, che_do: cheDo });
    tgNap();
  } catch (e) { await nhac(e.message); }
  $('#tgXayNut').disabled = false;
});

$('#tgThuLai').addEventListener('click', async () => {
  try {
    await api('/api/world/build', { url: TG.url });
    tgNap();
  } catch (e) { nhac(e.message); }
});

$('#tgHuyXay').addEventListener('click', () =>
  api('/api/world/cancel', { url: TG.url }).then(tgNap).catch(() => { }));

$('#tgXayLai').addEventListener('click', async () => {
  const ok = await hoi('Phân tích lại TỪ ĐẦU sẽ xoá sổ tay thế giới cũ và toàn bộ ghi chú '
    + 'phân tích (các phiên chơi vẫn được giữ).\n\nTruyện dài sẽ tốn khá nhiều thời gian. Làm lại?');
  if (!ok) return;
  try {
    await api('/api/world/build', { url: TG.url, lam_lai: true });
    tgNap();
  } catch (e) { nhac(e.message); }
});

function veSanSang(d) {
  tgView('tgSanSang');
  const m = d.meta || {};
  $('#tgMeta').textContent = `Sổ tay dựng từ ${m.chapters_total || '?'} chương`
    + (m.model ? ` · model ${m.model}` : '') + (m.mode === 'nhanh' ? ' · chế độ nhanh' : '');
  $('#tgSoTay').classList.add('hidden');
  $('#tgSoTay').innerHTML = '';
  vePhien(d.phien || []);
}

function vePhien(ds) {
  const luc = (t) => t ? new Date(t * 1000).toLocaleString('vi') : '';
  $('#tgDsPhien').innerHTML = ds.length ? ds.map((p) => `
    <div class="phien-card">
      <div class="t">${esc(p.ten)}</div>
      <div class="d">${p.so_chuong} chương${p.vi_tri ? ' · ' + esc(p.vi_tri) : ''}<br>${esc(luc(p.updated))}</div>
      <div class="acts">
        <button class="primary" data-choi="${esc(p.id)}">▶ Chơi tiếp</button>
        <button class="del" data-xoa-phien="${esc(p.id)}" data-ten="${esc(p.ten)}">Xoá</button>
      </div>
    </div>`).join('')
    : '<div class="empty">Chưa có lần chơi nào — tạo nhân vật để bước vào thế giới.</div>';
  $$('#tgDsPhien [data-choi]').forEach((b) => b.addEventListener('click', async () => {
    try {
      const d = await api('/api/world/session?url=' + enc(TG.url) + '&id=' + enc(b.dataset.choi));
      moChoi(d.phien);
    } catch (e) { nhac(e.message); }
  }));
  $$('#tgDsPhien [data-xoa-phien]').forEach((b) => b.addEventListener('click', async () => {
    const ok = await hoi(`Xoá lần chơi của "${b.dataset.ten}"? Toàn bộ chương đã sinh sẽ mất.`);
    if (!ok) return;
    await api('/api/world/session/delete', { url: TG.url, id: b.dataset.xoaPhien }).catch(() => { });
    tgNap();
  }));
}

$('#tgXemSoTay').addEventListener('click', async () => {
  const box = $('#tgSoTay');
  if (!box.classList.contains('hidden')) { box.classList.add('hidden'); return; }
  if (!box.innerHTML) {
    try {
      const d = await api('/api/world/info?url=' + enc(TG.url));
      const s = d.world.sections || {};
      box.innerHTML = Object.keys(TEN_MUC).filter((k) => s[k]).map((k) => `
        <details${k === 'bi_an' ? ' class="mat"' : ''}>
          <summary>${esc(TEN_MUC[k])}</summary>
          <div class="tg-md">${mdNho(s[k])}</div>
        </details>`).join('');
    } catch (e) { box.innerHTML = '<div class="notice err">' + esc(e.message) + '</div>'; }
  }
  box.classList.remove('hidden');
});

/* markdown thu nhỏ: đủ cho sổ tay AI viết (tiêu đề, đậm, gạch đầu dòng) */
function mdNho(text) {
  let out = '';
  let trongDs = false;
  for (let dong of String(text || '').split('\n')) {
    dong = dong.trimEnd();
    const nd = esc(dong).replace(/\*\*(.+?)\*\*/g, '<b>$1</b>');
    if (/^\s*[-*•+] /.test(dong)) {
      if (!trongDs) { out += '<ul>'; trongDs = true; }
      out += '<li>' + nd.replace(/^\s*[-*•+] /, '') + '</li>';
      continue;
    }
    if (trongDs) { out += '</ul>'; trongDs = false; }
    const h = dong.match(/^(#{1,6}) /);
    if (h) out += `<h${Math.min(5, h[1].length + 2)}>` + nd.replace(/^#+ /, '') + `</h${Math.min(5, h[1].length + 2)}>`;
    else if (dong.trim()) out += '<p>' + nd + '</p>';
  }
  if (trongDs) out += '</ul>';
  return out;
}

/* ---- tạo nhân vật ---- */
$('#tgTaoNVNut').addEventListener('click', () => {
  tgView('tgTaoNV');
  $('#nvBao').textContent = '';
});
$('#nvHuy').addEventListener('click', () => tgNap());

$('#nvOk').addEventListener('click', async () => {
  const ten = $('#nvTen').value.trim();
  if (!ten) { $('#nvBao').textContent = 'Nhân vật phải có tên đã chứ.'; return; }
  const nv = {
    ten,
    gioi_tinh: $('#nvGioiTinh').value.trim(),
    tuoi: $('#nvTuoi').value.trim(),
    xuat_than: $('#nvXuatThan').value.trim(),
    tinh_cach: $('#nvTinhCach').value.trim(),
    muc_tieu: $('#nvMucTieu').value.trim(),
    khoi_dau: $('#nvKhoiDau').value.trim(),
  };
  $('#nvOk').disabled = true;
  $('#nvBao').textContent = '✍ Quản trò đang viết chương mở đầu — thường mất 1–3 phút '
    + '(model trên máy có thể lâu hơn). Đừng tắt app…';
  try {
    const d = await api('/api/world/create', { url: TG.url, nhan_vat: nv });
    $('#nvBao').textContent = '';
    moChoi(d.phien);
  } catch (e) { $('#nvBao').textContent = 'Không tạo được: ' + e.message; }
  $('#nvOk').disabled = false;
});

/* ---- màn chơi: đọc từng chương như trình đọc, thanh chương bên trái ---- */
const TC = { phien: null, dangGui: false, xem: null };

function moChoi(phien) {
  TC.phien = phien;
  TC.dangGui = false;
  TC.xem = null;                       // null = mở ở chương mới nhất
  $('#tcTen').textContent = phien.nhan_vat.ten + ' — ' + TG.ten;
  $('#tcHanhDong').value = '';
  // desktop: mục lục luôn mở như trình đọc; màn hẹp thì thu lại
  $('#tcDsChuong').classList.toggle('hidden', matchMedia('(max-width:760px)').matches);
  $('#tcBang').classList.add('hidden');
  $('#tgChoi').classList.remove('hidden');
  veChoi(true);
}

function veChoi(veCuoi) {
  const p = TC.phien;
  if (!p || !p.chuong.length) return;
  const n = p.chuong.length;
  if (veCuoi || TC.xem == null || TC.xem >= n) TC.xem = n - 1;
  const c = p.chuong[TC.xem];
  const oCuoi = TC.xem === n - 1;
  const tt = p.trang_thai || {};
  $('#tcPhu').textContent = [tt.vi_tri, tt.thoi_gian, `chương ${TC.xem + 1}/${n}`]
    .filter(Boolean).join(' · ');

  // esc trước rồi mới đổi **đậm** — model hay nhấn vài chữ kiểu markdown
  const doan = (l) => '<p>' + esc(l).replace(/\*\*(.+?)\*\*/g, '<b>$1</b>') + '</p>';
  $('#tcNoiDung').innerHTML =
    (c.action && c.action !== '(mở đầu)' ? `<div class="tc-act">▸ ${esc(c.action)}</div>` : '')
    + `<div class="khung"><h2>${esc(c.title)}</h2>`
    + String(c.text).split(/\n+/).map(doan).join('')
    + (TC.dangGui && oCuoi ? '<div class="dang-viet">✍ Quản trò đang viết chương tiếp theo… '
      + '(model trên máy có thể mất vài phút)</div>' : '')
    + (!oCuoi ? '<button class="het-nut" id="tcChuongSau">Chương sau →</button>'
      : (TC.dangGui ? '' : '<p class="het">— Bạn đang ở hiện tại của câu chuyện — hành động bên dưới để viết tiếp —</p>'))
    + '</div>';
  const nutSau = $('#tcChuongSau');
  if (nutSau) nutSau.addEventListener('click', () => { TC.xem += 1; veChoi(false); });

  $('#tcDsChuong').innerHTML = p.chuong.map((ch, i) => `
    <button data-i="${i}"${i === TC.xem ? ' class="on"' : ''}>${esc(ch.title)}</button>`).join('');
  $$('#tcDsChuong button').forEach((b) => b.addEventListener('click', () => {
    TC.xem = Number(b.dataset.i);
    if (matchMedia('(max-width:760px)').matches) $('#tcDsChuong').classList.add('hidden');
    veChoi(false);
  }));
  const dangOn = $('#tcDsChuong button.on');
  if (dangOn) dangOn.scrollIntoView({ block: 'nearest' });

  // gợi ý chỉ hiện ở chương mới nhất; xem lại chương cũ thì hiện lối về
  if (oCuoi && !TC.dangGui) {
    $('#tcGoiY').innerHTML = (c.goi_y || []).map((g) =>
      `<button title="${esc(g)}">${esc(g)}</button>`).join('');
    $$('#tcGoiY button').forEach((b) => b.addEventListener('click', () => {
      $('#tcHanhDong').value = b.title;
      $('#tcHanhDong').focus();
    }));
  } else if (!oCuoi) {
    $('#tcGoiY').innerHTML =
      `<button id="tcVeCuoi">Đang xem lại chương cũ — về chương mới nhất (${n}) ↩</button>`;
    $('#tcVeCuoi').addEventListener('click', () => veChoi(true));
  } else {
    $('#tcGoiY').innerHTML = '';
  }

  veBangTrangThai();
  $('#tcNoiDung').scrollTop = (TC.dangGui && oCuoi) ? $('#tcNoiDung').scrollHeight : 0;
}

function veBangTrangThai() {
  const p = TC.phien;
  const tt = p.trang_thai || {};
  const nv = p.nhan_vat || {};
  const muc = (ten, gt) => gt ? `<h4>${ten}</h4><p>${esc(gt)}</p>` : '';
  const ds = (ten, arr) => (arr && arr.length)
    ? `<h4>${ten}</h4><ul>${arr.map((x) => '<li>' + esc(x) + '</li>').join('')}</ul>` : '';
  $('#tcBang').innerHTML =
    `<h4>Nhân vật</h4><p>${esc(nv.ten || '')}</p>`
    + (nv.xuat_than ? `<p class="m">${esc(nv.xuat_than)}</p>` : '')
    + muc('Vị trí', tt.vi_tri) + muc('Thời gian', tt.thoi_gian)
    + muc('Sức mạnh', tt.suc_manh) + muc('Thể trạng', tt.the_trang)
    + ds('Vật phẩm', tt.vat_pham) + ds('Quan hệ', tt.quan_he)
    + ds('Việc còn treo', (p.manh_moi || []).slice(-10))
    + ds('Biến động thế giới', (p.bien_dong || []).slice(-12))
    + (p.tom_tat ? `<h4>Hành trình</h4><p class="m">${esc(p.tom_tat)}</p>` : '');
}

async function tcGuiHanhDong() {
  if (TC.dangGui || !TC.phien) return;
  const hd = $('#tcHanhDong').value.trim();
  if (!hd) return;
  TC.dangGui = true;
  $('#tcGui').disabled = true;
  $('#tcHanhDong').disabled = true;
  veChoi(true);                        // về chương mới nhất, hiện "đang viết"
  try {
    const d = await api('/api/world/act', { url: TG.url, id: TC.phien.id, hanh_dong: hd });
    TC.phien = d.phien;
    $('#tcHanhDong').value = '';
    TC.dangGui = false;
    veChoi(true);                      // lật sang chương vừa sinh, đọc từ đầu
  } catch (e) {
    TC.dangGui = false;
    veChoi(true);
    await nhac('Không sinh được chương: ' + e.message + '\n\nHành động của bạn vẫn còn trong ô nhập — thử gửi lại.');
  }
  $('#tcGui').disabled = false;
  $('#tcHanhDong').disabled = false;
  $('#tcHanhDong').focus();
}

$('#tcGui').addEventListener('click', tcGuiHanhDong);
$('#tcHanhDong').addEventListener('keydown', (e) => {
  if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) { e.preventDefault(); tcGuiHanhDong(); }
});
$('#tcDong').addEventListener('click', () => {
  $('#tgChoi').classList.add('hidden');
  tgNap();                    // về màn thế giới thì cập nhật lại danh sách phiên
});
$('#tcMucLuc').addEventListener('click', () => {
  $('#tcDsChuong').classList.toggle('hidden');
  if (matchMedia('(max-width:760px)').matches) $('#tcBang').classList.add('hidden');
});
$('#tcTrangThai').addEventListener('click', () => {
  $('#tcBang').classList.toggle('hidden');
  if (matchMedia('(max-width:760px)').matches) $('#tcDsChuong').classList.add('hidden');
});

// chuyển chương bằng phím như trình đọc
document.addEventListener('keydown', (e) => {
  if ($('#tgChoi').classList.contains('hidden')) return;
  if (e.target.matches && e.target.matches('input, textarea, select')) return;
  if (e.key === 'ArrowLeft' && TC.xem > 0) { TC.xem -= 1; veChoi(false); }
  else if (e.key === 'ArrowRight' && TC.phien && TC.xem < TC.phien.chuong.length - 1) {
    TC.xem += 1; veChoi(false);
  } else if (e.key === 'Escape') {
    $('#tgChoi').classList.add('hidden');
    tgNap();
  }
});

/* ---- kiểm tra kết nối AI (tab Cài đặt) ---- */
$('#aiThu').addEventListener('click', async () => {
  const kq = $('#aiThuKq');
  kq.textContent = 'Đang hỏi máy chủ AI…';
  // dùng ngay giá trị đang gõ: lưu tạm rồi mới thử, khỏi bắt người dùng bấm Lưu trước
  try {
    await api('/api/settings', {
      cai_dat: {
        ai: {
          base_url: $('#aiUrl').value.trim(), api_key: $('#aiKey').value.trim(),
          model: $('#aiModel').value.trim(),
          temperature: Number($('#aiNhiet').value) || 0.8, max_tokens: 3000,
          timeout: Number($('#aiTimeout').value) || 600,
          chunk_chars: Number($('#aiChunk').value) || 20000,
          num_ctx: Number($('#aiCtx').value) || 24576,
          trau_chuot: $('#aiTrauChuot').checked,
        },
      },
    });
    const d = await api('/api/ai/models');
    $('#aiDsModel').innerHTML = d.models.map((m) => `<option value="${esc(m)}">`).join('');
    kq.textContent = d.models.length
      ? '✓ Kết nối được. Model đang có: ' + d.models.slice(0, 12).join(', ')
      + (d.models.length > 12 ? '…' : '')
      : '✓ Kết nối được nhưng máy chủ chưa có model nào (Ollama: chạy "ollama pull qwen3:8b").';
  } catch (e) { kq.textContent = '✗ ' + e.message; }
});

$('#mtCapNhat').addEventListener('click', async () => {
  const nut = $('#mtCapNhat');
  nut.disabled = true;
  $('#mtBao').textContent = 'Đang đọc lại trang nguồn để tìm chương mới… '
    + '(truyện dài có thể mất một lúc)';
  try {
    const d = await api('/api/library/update', { url: KHO.url });
    if (d.canh_bao) await nhac(d.canh_bao);
    if (d.moi > 0) {
      $('#mtBao').textContent = `Có ${d.moi} chương mới (nguồn đang có ${d.tong} chương). `
        + 'Đang tải — xem tiến độ ở tab Đang tải. Tải xong thì đóng truyện này '
        + 'rồi mở lại là thấy chương mới.';
      napViec();
    } else {
      $('#mtBao').textContent = `Đã là mới nhất — nguồn cũng chỉ có ${d.tong} chương.`;
    }
  } catch (e) {
    $('#mtBao').textContent = 'Không kiểm tra được: ' + e.message;
  }
  nut.disabled = false;
});

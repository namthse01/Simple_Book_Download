'use strict';
/* ================= ĐỌC BÁO =================
   Đọc ngay trong app: toà soạn nào tự phát cả bài trong RSS thì hiện trọn bài
   kèm ảnh/video; còn lại thì nhúng thẳng trang báo vào cửa sổ app. Chỉ báo nào
   chặn nhúng mới phải mở ra trình duyệt. */

const BAO = {
  nap: false, ngay: '', muc: '', quoc: '', tim: '',
  tu: 0, so: 60, tong: 0, bai: [],
  meta: { quoc_gia: [], the_loai: [], nguon: [] },
  dangTai: false, hen: 0,
};

const tenMuc = (ma) => (BAO.meta.the_loai.find((m) => m.ma === ma) || {}).ten || ma;
const coQuoc = (ma) => (BAO.meta.quoc_gia.find((q) => q.ma === ma) || {}).co || '🌐';

function baoBao(msg, kind) {
  const el = $('#bBao');
  el.textContent = msg || '';
  el.className = 'notice ' + (kind || '');
  el.classList.toggle('hidden', !msg);
}

async function moTabBao() {
  if (BAO.nap) return;
  BAO.nap = true;
  try {
    const [n, c] = await Promise.all([api('/api/bao/nguon'), api('/api/settings')]);
    BAO.meta = { quoc_gia: n.quoc_gia, the_loai: n.the_loai, nguon: n.nguon };
    $('#bNgonNgu').value = c.cai_dat.bao_ngon_ngu || 'vi';
    $('#bTuDich').checked = !!c.cai_dat.bao_tu_dich;
  } catch (e) { baoBao('Không đọc được danh sách nguồn: ' + e.message, 'err'); }
  await napNgayBao();
  theoDoiViecBao();
}

async function napNgayBao() {
  let d;
  try { d = await api('/api/bao/ngay'); } catch (e) { return baoBao('Lỗi: ' + e.message, 'err'); }
  const sel = $('#bChonNgay');
  sel.innerHTML = d.ngay.map((x) =>
    '<option value="' + x.ngay + '">' + x.ngay + ' — ' + x.so_bai + ' tin</option>').join('');
  if (!d.ngay.length) {
    $('#bNgayNhan').textContent = '';
    $('#bMuc').innerHTML = '';
    $('#bQuoc').innerHTML = '';
    $('#bDs').innerHTML = '';
    $('#bThem').classList.add('hidden');
    const bat = BAO.meta.nguon.filter((x) => !x.tat).length;
    return baoBao('Kho báo đang trống — bấm “Cập nhật tin hôm nay” để lấy tin từ '
      + bat + ' nguồn của 9 nước.', 'info');
  }
  if (!d.ngay.some((x) => x.ngay === BAO.ngay)) BAO.ngay = d.ngay[0].ngay;
  sel.value = BAO.ngay;
  await napDsBao(true);
}

async function napDsBao(moi) {
  if (BAO.dangTai) return;
  BAO.dangTai = true;
  if (moi) { BAO.tu = 0; BAO.bai = []; }
  try {
    const q = new URLSearchParams({
      ngay: BAO.ngay, muc: BAO.muc, quoc: BAO.quoc, tim: BAO.tim,
      tu: String(BAO.tu), so: String(BAO.so),
    });
    const d = await api('/api/bao/doc?' + q.toString());
    BAO.tong = d.tong;
    BAO.bai = moi ? d.bai : BAO.bai.concat(d.bai);
    BAO.tu = BAO.bai.length;
    $('#bNgayNhan').textContent = d.cap_nhat_luc
      ? '· cập nhật ' + d.cap_nhat_luc.replace('T', ' ').slice(0, 16) : '';
    if (moi) veChipsBao(d.thong_ke);
    veBaiBao();
    baoBao(BAO.bai.length ? '' : 'Không có tin nào khớp.', 'info');
  } catch (e) { baoBao('Lỗi: ' + e.message, 'err'); }
  BAO.dangTai = false;
  if (moi && $('#bTuDich').checked && $('#bNgonNgu').value !== 'goc') dichMucBao(true);
}

function veChipsBao(thongKe) {
  thongKe = thongKe || {};
  const tong = Object.values(thongKe).reduce((a, b) => a + b, 0);
  const muc = [{ ma: '', ten: 'Tất cả', n: tong }].concat(
    BAO.meta.the_loai.filter((m) => thongKe[m.ma])
      .map((m) => ({ ma: m.ma, ten: m.ten, n: thongKe[m.ma] })));
  $('#bMuc').innerHTML = muc.map((m) =>
    '<button data-m="' + m.ma + '" class="' + (m.ma === BAO.muc ? 'on' : '') + '">'
    + esc(m.ten) + '<span class="n">' + m.n + '</span></button>').join('');
  $$('#bMuc button').forEach((b) => b.addEventListener('click', () => {
    BAO.muc = b.dataset.m;
    napDsBao(true);
  }));

  const quoc = [{ ma: '', ten: 'Mọi nước', co: '' }].concat(BAO.meta.quoc_gia);
  $('#bQuoc').innerHTML = quoc.map((q) =>
    '<button data-q="' + q.ma + '" class="' + (q.ma === BAO.quoc ? 'on' : '') + '">'
    + (q.co || '') + ' ' + esc(q.ten) + '</button>').join('');
  $$('#bQuoc button').forEach((b) => b.addEventListener('click', () => {
    BAO.quoc = b.dataset.q;
    napDsBao(true);
  }));
}

function veBaiBao() {
  const ngonNgu = $('#bNgonNgu').value;
  $('#bDs').innerHTML = BAO.bai.map((b, i) => {
    const d = (b.dich && b.dich.lang === ngonNgu) ? b.dich : null;
    const td = (d && d.tieu_de) || b.tieu_de;
    const tt = (d && d.tom_tat) || b.tom_tat;
    const gio = b.luc && b.luc.length >= 16 ? b.luc.slice(11, 16) : '';
    const daDich = !!(d && d.tieu_de && d.tieu_de !== b.tieu_de);
    return '<article class="bai">'
      + '<p class="td"><a href="#" data-mo="' + i + '">' + esc(td) + '</a></p>'
      + (daDich ? '<p class="goc">' + esc(b.tieu_de) + '</p>' : '')
      + (tt ? '<p class="tt">' + esc(tt) + '</p>' : '')
      + '<div class="chan">'
      + '<span>' + coQuoc(b.quoc) + '</span>'
      + '<span class="bao-ten">' + esc(b.nguon) + '</span>'
      + (gio ? '<span>· ' + gio + '</span>' : '')
      + '<span>· ' + esc(tenMuc(b.muc)) + '</span>'
      + (daDich ? '<span class="dau-dich">đã dịch</span>' : '')
      + ((b.cung_dua || []).length
        ? '<span>· ' + b.cung_dua.length + ' báo khác cùng đưa</span>' : '')
      + '</div></article>';
  }).join('');
  $$('#bDs [data-mo]').forEach((a) => a.addEventListener('click', (e) => {
    e.preventDefault();
    moBaiBao(Number(a.dataset.mo));
  }));
  $('#bThem').classList.toggle('hidden', BAO.bai.length >= BAO.tong);
  $('#bThem').textContent = 'Xem thêm ↓ (' + BAO.bai.length + '/' + BAO.tong + ')';
}

/* ---------- cập nhật + dịch: chạy nền, theo dõi tiến độ ---------- */
async function theoDoiViecBao() {
  clearTimeout(BAO.hen);
  let d;
  try { d = await api('/api/bao/tien-do'); } catch (e) { return; }
  const v = d.viec;
  const el = $('#bViec');
  $('#bCapNhat').disabled = v.dang;
  $('#bDich').disabled = v.dang;
  if (v.dang) {
    const pct = v.tong ? Math.round((v.xong * 100) / v.tong) : 0;
    el.className = 'notice info';
    el.textContent = (v.loai === 'dich' ? 'Đang dịch… ' : 'Đang lấy tin… ')
      + v.xong + '/' + v.tong + ' (' + pct + '%) ' + (v.ten || '');
    el.classList.remove('hidden');
    BAO.hen = setTimeout(theoDoiViecBao, 900);
    return;
  }
  if (v.loi) {
    el.className = 'notice err';
    el.textContent = 'Lỗi: ' + v.loi;
    el.classList.remove('hidden');
    return;
  }
  // chỉ báo kết quả một lần, ngay sau khi việc vừa xong
  if (v.ket_qua && v.xong_luc && v.xong_luc !== BAO.daBao) {
    BAO.daBao = v.xong_luc;
    const k = v.ket_qua;
    el.className = 'notice';
    el.textContent = v.loai === 'dich'
      ? 'Đã dịch ' + (k.da_luu || k.so_dich || 0) + ' tin.' + (k.loi ? ' ' + k.loi : '')
      : 'Xong: ' + k.so_bai + ' tin từ ' + k.so_nguon + ' nguồn.'
        + (k.loi && k.loi.length
          ? ' ' + k.loi.length + ' nguồn lỗi: ' + k.loi.slice(0, 3).join(', ') : '');
    el.classList.remove('hidden');
    setTimeout(() => el.classList.add('hidden'), 12000);
    if (v.loai === 'dich') await napDsBao(true);
    else await napNgayBao();
  }
}

$('#bCapNhat').addEventListener('click', async () => {
  try {
    await api('/api/bao/cap-nhat', {});
    theoDoiViecBao();
  } catch (e) { baoBao('Không chạy được: ' + e.message, 'err'); }
});

async function dichMucBao(tuDong) {
  const sang = $('#bNgonNgu').value;
  if (sang === 'goc') {
    if (!tuDong) nhac('Đang để “Giữ nguyên gốc” — chọn ngôn ngữ đích trước đã.');
    return;
  }
  try {
    const d = await api('/api/bao/dich', {
      ngay: BAO.ngay, muc: BAO.muc, quoc: BAO.quoc, tim: BAO.tim, so: BAO.so, sang: sang,
    });
    if (d.xong_ngay) {
      if (!tuDong) baoBao('Mục này đã dịch xong cả rồi.', 'info');
      return;
    }
    theoDoiViecBao();
  } catch (e) { if (!tuDong) baoBao('Không dịch được: ' + e.message, 'err'); }
}

$('#bDich').addEventListener('click', () => dichMucBao(false));
$('#bThem').addEventListener('click', () => napDsBao(false));
$('#bChonNgay').addEventListener('change', () => {
  BAO.ngay = $('#bChonNgay').value;
  napDsBao(true);
});
$('#bTim').addEventListener('keydown', (e) => {
  if (e.key === 'Enter') { BAO.tim = $('#bTim').value.trim(); napDsBao(true); }
});
$('#bTim').addEventListener('search', () => {
  BAO.tim = $('#bTim').value.trim();
  napDsBao(true);
});
$('#bNgonNgu').addEventListener('change', async () => {
  await api('/api/settings', { cai_dat: { bao_ngon_ngu: $('#bNgonNgu').value } }).catch(() => { });
  veBaiBao();
  if ($('#bTuDich').checked) dichMucBao(true);
});
$('#bTuDich').addEventListener('change', () => {
  api('/api/settings', { cai_dat: { bao_tu_dich: $('#bTuDich').checked } }).catch(() => { });
  if ($('#bTuDich').checked) dichMucBao(true);
});
$('#bThuMuc').addEventListener('click', async () => {
  try {
    const d = await api('/api/bao/ngay');
    api('/api/open', { duong_dan: d.thu_muc }).catch(() => { });
  } catch (e) { /* bỏ qua */ }
});

/* ---------- quản lý nguồn báo ---------- */
$('#bNguon').addEventListener('click', moNguonBao);
$('#nbDong').addEventListener('click', () => $('#manNguonBao').classList.add('hidden'));

async function moNguonBao() {
  try {
    const d = await api('/api/bao/nguon');
    BAO.meta = { quoc_gia: d.quoc_gia, the_loai: d.the_loai, nguon: d.nguon };
  } catch (e) { return nhac('Không đọc được danh sách nguồn: ' + e.message); }
  const dsQuoc = BAO.meta.quoc_gia.map((q) =>
    '<option value="' + q.ma + '">' + q.co + ' ' + esc(q.ten) + '</option>').join('');
  $('#nbLocQuoc').innerHTML = '<option value="">Mọi nước</option>' + dsQuoc;
  $('#nbQuoc').innerHTML = dsQuoc + '<option value="khac">🌐 Nước khác</option>';
  $('#nbMuc').innerHTML = '<option value="">Tự đoán thể loại</option>'
    + BAO.meta.the_loai.map((m) =>
      '<option value="' + m.ma + '">' + esc(m.ten) + '</option>').join('');
  $('#nbBao').textContent = '';
  veDsNguonBao();
  $('#manNguonBao').classList.remove('hidden');
}

function veDsNguonBao() {
  const q = $('#nbLocQuoc').value;
  const ten = $('#nbLocTen').value.trim().toLowerCase();
  const ds = BAO.meta.nguon.filter((n) => (!q || n.quoc === q)
    && (!ten || n.ten.toLowerCase().includes(ten)));
  $('#nbDem').textContent = BAO.meta.nguon.filter((n) => !n.tat).length
    + '/' + BAO.meta.nguon.length + ' nguồn đang bật';
  $('#nbDs').innerHTML = ds.length ? ds.map((n) =>
    '<div class="nb-mot ' + (n.tat ? 'tat' : '') + '">'
    + '<input type="checkbox" data-bat="' + esc(n.ma) + '" ' + (n.tat ? '' : 'checked') + '>'
    + '<label class="ten"><b>' + coQuoc(n.quoc) + ' ' + esc(n.ten) + '</b>'
    + '<small>' + esc(n.url) + '</small></label>'
    + '<span class="muted" style="font-size:.74rem">'
    + (n.muc ? esc(tenMuc(n.muc)) : 'tự đoán') + '</span>'
    + '<button class="xoa" data-xoa="' + esc(n.ma) + '" data-ten="' + esc(n.ten)
    + '">Xoá</button></div>').join('')
    : '<div class="hint">Không có nguồn nào khớp bộ lọc.</div>';

  $$('#nbDs [data-bat]').forEach((c) => c.addEventListener('change', async () => {
    try {
      const d = await api('/api/bao/nguon/sua', { ma: c.dataset.bat, tat: !c.checked });
      BAO.meta.nguon = d.nguon;
      veDsNguonBao();
    } catch (e) { $('#nbBao').textContent = 'Lỗi: ' + e.message; }
  }));
  $$('#nbDs [data-xoa]').forEach((b) => b.addEventListener('click', async () => {
    if (!await hoi('Xoá nguồn “' + b.dataset.ten + '” khỏi danh sách?')) return;
    try {
      const d = await api('/api/bao/nguon/xoa', { ma: b.dataset.xoa });
      BAO.meta.nguon = d.nguon;
      veDsNguonBao();
    } catch (e) { $('#nbBao').textContent = 'Lỗi: ' + e.message; }
  }));
}

$('#nbLocQuoc').addEventListener('change', veDsNguonBao);
$('#nbLocTen').addEventListener('input', veDsNguonBao);

async function batTatHet(tat) {
  const q = $('#nbLocQuoc').value;
  const ds = BAO.meta.nguon.filter((n) => (!q || n.quoc === q) && n.tat !== tat);
  $('#nbBao').textContent = 'Đang ' + (tat ? 'tắt' : 'bật') + ' ' + ds.length + ' nguồn…';
  for (const n of ds) {
    try {
      const d = await api('/api/bao/nguon/sua', { ma: n.ma, tat: tat });
      BAO.meta.nguon = d.nguon;
    } catch (e) { /* nguồn nào lỗi thì bỏ qua, làm tiếp cái sau */ }
  }
  $('#nbBao').textContent = '';
  veDsNguonBao();
}
$('#nbBatHet').addEventListener('click', () => batTatHet(false));
$('#nbTatHet').addEventListener('click', () => batTatHet(true));

function nguonMoiTuForm() {
  return {
    ten: $('#nbTen').value.trim(), url: $('#nbUrl').value.trim(),
    quoc: $('#nbQuoc').value, lang: $('#nbLang').value, muc: $('#nbMuc').value,
  };
}

$('#nbThu').addEventListener('click', async () => {
  const n = nguonMoiTuForm();
  if (!n.url) { $('#nbBao').textContent = 'Dán địa chỉ RSS vào đã.'; return; }
  $('#nbBao').textContent = 'Đang thử đọc feed…';
  try {
    const d = await api('/api/bao/nguon/thu', n);
    $('#nbBao').textContent = 'Đọc được ' + d.so_bai + ' bài. Ví dụ: '
      + d.vi_du.map((v) => '“' + v.tieu_de.slice(0, 40) + '” → ' + tenMuc(v.muc)).join(' · ');
  } catch (e) { $('#nbBao').textContent = 'Không đọc được: ' + e.message; }
});

$('#nbLuu').addEventListener('click', async () => {
  const n = nguonMoiTuForm();
  if (!n.ten || !n.url) { $('#nbBao').textContent = 'Cần cả tên báo và địa chỉ RSS.'; return; }
  try {
    const d = await api('/api/bao/nguon/them', n);
    BAO.meta.nguon = d.nguon;
    $('#nbTen').value = '';
    $('#nbUrl').value = '';
    $('#nbBao').textContent = 'Đã thêm “' + n.ten + '”. Bấm Cập nhật để lấy tin từ nguồn này.';
    veDsNguonBao();
  } catch (e) { $('#nbBao').textContent = 'Không thêm được: ' + e.message; }
});

/* ---------- đọc bài ngay trong app ----------
   Hai lớp, theo đúng thứ tự:
   1. Toà soạn tự phát cả bài trong RSS (content:encoded) -> hiện trọn bài kèm
      ảnh/video ngay trong app.
   2. Không có thì nhúng thẳng trang báo vào cửa sổ app — vẫn đọc trong app,
      đủ ảnh/video, do chính trang của họ phục vụ.
   Báo nào chặn nhúng thì mới cần mở bằng trình duyệt. */
BAO.dangDoc = -1;

function moBaiBao(i) {
  const b = BAO.bai[i];
  if (!b) return;
  BAO.dangDoc = i;
  const sang = $('#bNgonNgu').value;
  const d = (b.dich && b.dich.lang === sang) ? b.dich : null;
  $('#dbTenBao').textContent = coQuoc(b.quoc) + ' ' + b.nguon;
  $('#dbTieuDe').textContent = (d && d.tieu_de) || b.tieu_de;
  const daDich = !!(d && d.tieu_de && d.tieu_de !== b.tieu_de);
  $('#dbGoc').textContent = daDich ? b.tieu_de : '';
  $('#dbGoc').classList.toggle('hidden', !daDich);
  const tt = (d && d.tom_tat) || b.tom_tat;
  $('#dbTomTat').textContent = tt || '';
  $('#dbTomTat').classList.toggle('hidden', !tt);
  const gio = b.luc && b.luc.length >= 16 ? b.luc.slice(0, 16).replace('T', ' ') : '';
  $('#dbChan').textContent = [b.nguon, gio, tenMuc(b.muc)].filter(Boolean).join(' · ');
  $('#dbTruoc').disabled = i <= 0;
  $('#dbSau').disabled = i >= BAO.bai.length - 1;
  $('#docBao').classList.remove('hidden');
  hienThanBai(b);
}

async function hienThanBai(b) {
  const khungBai = $('#dbBai');
  const frame = $('#dbFrame');
  const bao = $('#dbBao');
  khungBai.classList.add('hidden');
  khungBai.innerHTML = '';
  frame.classList.add('hidden');
  frame.src = 'about:blank';
  khungBai.scrollTop = 0;
  BAO.baiDangDoc = null;
  $('#dbDich').disabled = true;
  $('#dbGocBan').classList.add('hidden');

  if (!b.link) {
    bao.className = 'notice';
    bao.textContent = 'Tin này không kèm link bài gốc.';
    bao.classList.remove('hidden');
    return;
  }

  // Lấy đúng bài đang mở về để đọc — và để bộ dịch với tới được chữ.
  bao.className = 'notice info';
  bao.textContent = 'Đang lấy nội dung bài…';
  bao.classList.remove('hidden');
  try {
    const d = await api('/api/bao/tai-bai', { ngay: BAO.ngay, link: b.link });
    if (BAO.bai[BAO.dangDoc] !== b) return;       // đã chuyển sang bài khác
    BAO.baiDangDoc = d.bai;
    bao.classList.add('hidden');
    khungBai.innerHTML = d.bai.noi_dung || '';
    khungBai.classList.remove('hidden');
    $('#dbDich').disabled = false;
    const sang = $('#bNgonNgu').value;
    if (d.bai.dich_bai && d.bai.dich_bai.lang === sang) apDungDichBai(d.bai.dich_bai.doan);
    else if ($('#bTuDich').checked && sang !== 'goc' && (b.lang || '') !== sang) dichBaiNay(true);
    return;
  } catch (e) {
    bao.className = 'notice';
    bao.textContent = 'Không bóc được nội dung bài (' + e.message
      + ') — thử hiển thị thẳng trang báo…';
  }

  // Bóc hụt thì nhúng trang báo vào app (vẫn ở trong app, nhưng bộ dịch
  // không can thiệp được vào trang của họ).
  let kq = { cho_nhung: false, ly_do: '' };
  try {
    kq = await api('/api/bao/nhung?url=' + encodeURIComponent(b.link));
  } catch (e) { kq.ly_do = e.message; }
  if (BAO.bai[BAO.dangDoc] !== b) return;
  if (kq.cho_nhung) {
    bao.classList.add('hidden');
    frame.src = b.link;
    frame.classList.remove('hidden');
  } else {
    bao.className = 'notice';
    bao.textContent = 'Không lấy được nội dung bài này, và báo cũng chặn hiển thị '
      + 'trong khung app (' + (kq.ly_do || 'bị chặn') + ').\n'
      + 'Bấm “Mở trang báo” ở trên để đọc bên trang của họ.';
    bao.classList.remove('hidden');
  }
}

/* Thay chữ từng đoạn bằng bản dịch, ảnh/video giữ nguyên chỗ cũ. */
function apDungDichBai(doan) {
  const khung = $('#dbBai');
  khung.querySelectorAll('[data-d]').forEach((el) => {
    const i = Number(el.dataset.d);
    if (doan[i] === undefined) return;
    if (el.dataset.goc === undefined) el.dataset.goc = el.textContent;
    el.textContent = doan[i];
  });
  $('#dbGocBan').classList.remove('hidden');
  $('#dbGocBan').textContent = 'Xem bản gốc';
  BAO.dangHienDich = true;
}

function doiGocDich() {
  const khung = $('#dbBai');
  const hienGoc = BAO.dangHienDich;
  khung.querySelectorAll('[data-d]').forEach((el) => {
    if (el.dataset.goc === undefined) return;
    const cu = el.textContent;
    el.textContent = el.dataset.goc;
    el.dataset.goc = cu;
  });
  BAO.dangHienDich = !hienGoc;
  $('#dbGocBan').textContent = hienGoc ? 'Xem bản dịch' : 'Xem bản gốc';
}

async function dichBaiNay(tuDong) {
  const b = BAO.bai[BAO.dangDoc];
  const sang = $('#bNgonNgu').value;
  if (!b || !BAO.baiDangDoc) return;
  if (sang === 'goc') {
    if (!tuDong) nhac('Đang để “Giữ nguyên gốc” — chọn ngôn ngữ đích ở trên đã.');
    return;
  }
  const bao = $('#dbBao');
  bao.className = 'notice info';
  bao.textContent = 'Đang dịch bài…';
  bao.classList.remove('hidden');
  $('#dbDich').disabled = true;
  try {
    const d = await api('/api/bao/dich-bai', { ngay: BAO.ngay, link: b.link, sang: sang });
    if (d.xong_ngay) {
      apDungDichBai(d.doan);
      bao.classList.add('hidden');
      $('#dbDich').disabled = false;
      return;
    }
    // chạy nền: chờ xong rồi lấy lại bài kèm bản dịch
    for (let i = 0; i < 400; i++) {
      await new Promise((r) => setTimeout(r, 1200));
      const t = await api('/api/bao/tien-do');
      if (!t.viec.dang) break;
      bao.textContent = 'Đang dịch bài… ' + t.viec.xong + '/' + t.viec.tong + ' đoạn';
    }
    const lai = await api('/api/bao/bai?ngay=' + encodeURIComponent(BAO.ngay)
      + '&link=' + encodeURIComponent(b.link));
    if (lai.bai.dich_bai && lai.bai.dich_bai.lang === sang) {
      BAO.baiDangDoc = lai.bai;
      apDungDichBai(lai.bai.dich_bai.doan);
      bao.classList.add('hidden');
    } else {
      bao.className = 'notice err';
      bao.textContent = 'Chưa dịch được bài này.';
    }
  } catch (e) {
    bao.className = 'notice err';
    bao.textContent = 'Không dịch được: ' + e.message;
  }
  $('#dbDich').disabled = false;
}

$('#dbDich').addEventListener('click', () => dichBaiNay(false));
$('#dbGocBan').addEventListener('click', doiGocDich);

function dongBaiBao() {
  $('#docBao').classList.add('hidden');
  $('#dbFrame').src = 'about:blank';
}

$('#dbDong').addEventListener('click', dongBaiBao);
$('#dbTruoc').addEventListener('click', () => moBaiBao(BAO.dangDoc - 1));
$('#dbSau').addEventListener('click', () => moBaiBao(BAO.dangDoc + 1));
$('#dbTrinhDuyet').addEventListener('click', () => {
  const b = BAO.bai[BAO.dangDoc];
  if (b && b.link) api('/api/open', { duong_dan: b.link }).catch(() => { });
});
document.addEventListener('keydown', (e) => {
  if ($('#docBao').classList.contains('hidden')) return;
  if (e.target.matches('input, textarea, select')) return;
  if (e.key === 'Escape') dongBaiBao();
  else if (e.key === 'ArrowLeft') moBaiBao(BAO.dangDoc - 1);
  else if (e.key === 'ArrowRight') moBaiBao(BAO.dangDoc + 1);
});

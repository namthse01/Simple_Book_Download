'use strict';
/* ========== Nhập tài liệu từ web ==========
   Dò các link file tài liệu trong trang đã cho, cho người dùng tick chọn,
   rồi tải về và đẩy qua bộ nhập tài liệu sẵn có (core/importer.py). */

const CAO = { file: [], hen: 0 };

function caoBao(msg, kind) {
  const el = $('#caoBao');
  el.textContent = msg || '';
  el.className = 'notice ' + (kind || '');
  el.classList.toggle('hidden', !msg);
}

$('#btCaoWeb').addEventListener('click', () => {
  $('#manCao').classList.remove('hidden');
  caoBao('');
  napNguonCao();
  if (!CAO.file.length) $('#caoUrl').focus();
});
$('#caoDong').addEventListener('click', () => $('#manCao').classList.add('hidden'));

function veDsCao() {
  const ds = CAO.file;
  $('#caoThanh').classList.toggle('hidden', !ds.length);
  $('#caoDs').innerHTML = ds.map((f, i) =>
    '<label class="cao-mot ' + (f.doc_duoc ? '' : 'kho') + '">'
    + '<input type="checkbox" data-i="' + i + '" ' + (f.doc_duoc ? 'checked' : '') + '>'
    + '<span class="ten"><b>' + esc(f.ten) + '</b>'
    + '<small>' + esc(f.nhan || f.tieu_de_trang || f.tu_trang) + '</small></span>'
    + '<span class="duoi">' + esc(f.duoi || '?') + '</span></label>').join('');
  $$('#caoDs input[type=checkbox]').forEach((c) =>
    c.addEventListener('change', capNhatDemCao));
  capNhatDemCao();
}

function capNhatDemCao() {
  const chon = $$('#caoDs input[type=checkbox]:checked').length;
  const kho = CAO.file.filter((f) => !f.doc_duoc).length;
  $('#caoDem').textContent = 'chọn ' + chon + '/' + CAO.file.length + ' file'
    + (kho ? ' · ' + kho + ' file định dạng app chưa đọc được' : '');
  $('#caoNhap').disabled = !chon;
  $('#caoNhap').textContent = chon ? 'Nhập ' + chon + ' file vào thư viện'
    : 'Nhập vào thư viện';
}

$('#caoChonHet').addEventListener('change', () => {
  const bat = $('#caoChonHet').checked;
  $$('#caoDs input[type=checkbox]').forEach((c, i) => {
    c.checked = bat && (CAO.file[i] || {}).doc_duoc !== false;
  });
  capNhatDemCao();
});

async function choXongCao(nhan) {
  for (let i = 0; i < 1200; i++) {
    await new Promise((r) => setTimeout(r, 900));
    const t = await api('/api/cao/tien-do');
    const v = t.viec;
    if (!v.dang) return v;
    caoBao(nhan + ' ' + v.xong + '/' + v.tong + (v.ten ? ' — ' + v.ten.slice(0, 70) : ''),
      'info');
  }
  return null;
}

$('#caoDo').addEventListener('click', async () => {
  const dia_chi = $('#caoUrl').value.split('\n').map((s) => s.trim()).filter(Boolean);
  if (!dia_chi.length) { caoBao('Dán địa chỉ trang vào đã.', 'err'); return; }
  $('#caoDo').disabled = true;
  CAO.file = [];
  veDsCao();
  caoBao('Đang dò…', 'info');
  try {
    await api('/api/cao/do', {
      dia_chi: dia_chi, sau: Number($('#caoSau').value),
      max_trang: Number($('#caoMaxTrang').value) || 60,
    });
    const v = await choXongCao('Đang dò trang');
    if (!v) { caoBao('Dò lâu quá, dừng theo dõi.', 'err'); }
    else if (v.loi) { caoBao('Lỗi: ' + v.loi, 'err'); }
    else {
      CAO.file = (v.ket_qua && v.ket_qua.file) || [];
      veDsCao();
      const loi = (v.ket_qua && v.ket_qua.loi) || [];
      caoBao('Dò xong ' + v.ket_qua.so_trang_da_do + ' trang, thấy '
        + CAO.file.length + ' file.'
        + (loi.length ? ' ' + loi.length + ' trang lỗi/bị chặn.' : ''),
        CAO.file.length ? '' : 'err');
      $('#caoTheoDoiKhung').classList.toggle('hidden', !CAO.file.length);
    }
  } catch (e) { caoBao('Không dò được: ' + e.message, 'err'); }
  $('#caoDo').disabled = false;
});

$('#caoNhap').addEventListener('click', async () => {
  const chon = $$('#caoDs input[type=checkbox]:checked').map((c) => CAO.file[Number(c.dataset.i)]);
  if (!chon.length) return;
  const ten = {};
  chon.forEach((f) => { ten[f.url] = f.ten; });
  $('#caoNhap').disabled = true;
  $('#caoDo').disabled = true;
  caoBao('Đang tải…', 'info');
  try {
    // Ghi nguồn vào sổ theo dõi TRƯỚC khi nhập, kèm mọi địa chỉ file vừa dò ra —
    // có danh sách đó thì bước nhập mới đánh dấu được "đã lấy", vì file tài liệu
    // hay nằm ở tên miền khác trang (CDN, GitHub Releases).
    const dc = $('#caoUrl').value.split('\n').map((x) => x.trim()).filter(Boolean);
    if ($('#caoTheoDoi').checked && dc.length
      && !$('#caoTheoDoiKhung').classList.contains('hidden')) {
      await api('/api/cao/nguon/them', {
        dia_chi: dc, sau: Number($('#caoSau').value),
        max_trang: Number($('#caoMaxTrang').value) || 60,
        tung_thay: CAO.file.map((f) => f.url),
      }).catch(() => { });
    }
    await api('/api/cao/nhap', { urls: chon.map((f) => f.url), ten: ten });
    const v = await choXongCao('Đang tải và nhập');
    if (!v) caoBao('Chạy lâu quá, dừng theo dõi.', 'err');
    else if (v.loi) caoBao('Lỗi: ' + v.loi, 'err');
    else {
      const k = v.ket_qua || {};
      const n = (k.sach || []).length;
      caoBao('Đã nhập ' + n + ' tài liệu vào thư viện.'
        + ((k.loi || []).length ? '\nKhông nhập được: ' + k.loi.slice(0, 5).join('; ') : ''),
        n ? '' : 'err');
      napNguonCao();
      napKho();
    }
  } catch (e) { caoBao('Không nhập được: ' + e.message, 'err'); }
  $('#caoNhap').disabled = false;
  $('#caoDo').disabled = false;
  capNhatDemCao();
});

/* ---------- theo dõi nguồn: lần sau chỉ hiện tài liệu MỚI ---------- */
async function napNguonCao() {
  let ds = [];
  try { ds = (await api('/api/cao/nguon')).nguon || []; } catch (e) { return; }
  CAO.nguon = ds;
  $('#caoNguon').innerHTML = ds.length ? ds.map((n) =>
    '<div class="mot"><span class="ten"><b>' + esc(n.ten) + '</b><small>'
    + esc(n.dia_chi[0]) + (n.dia_chi.length > 1 ? ' +' + (n.dia_chi.length - 1) + ' trang' : '')
    + '</small></span>'
    + '<span class="' + (n.moi ? 'co-moi' : 'muted') + '">'
    + (n.moi ? n.moi + ' mới' : n.so_da_nhap + ' đã nhập') + '</span>'
    + '<button data-kiem="' + esc(n.ma) + '">Kiểm tra</button>'
    + '<button class="xoa" data-bo="' + esc(n.ma) + '">✕</button></div>').join('')
    : '<div class="trong">Chưa theo dõi trang nào. Dò một trang rồi tick '
      + '“Theo dõi trang này” là xong.</div>';
  $$('#caoNguon [data-kiem]').forEach((b) =>
    b.addEventListener('click', () => kiemTraMoi(b.dataset.kiem)));
  $$('#caoNguon [data-bo]').forEach((b) => b.addEventListener('click', async () => {
    try {
      await api('/api/cao/nguon/xoa', { ma: b.dataset.bo });
      napNguonCao();
    } catch (e) { caoBao('Không xoá được: ' + e.message, 'err'); }
  }));
}

async function kiemTraMoi(ma) {
  $('#caoKiemHet').disabled = true;
  $('#caoDo').disabled = true;
  CAO.file = [];
  veDsCao();
  $('#caoTheoDoiKhung').classList.add('hidden');
  caoBao('Đang kiểm tra tài liệu mới…', 'info');
  try {
    await api('/api/cao/kiem-tra', { ma: ma || '' });
    const v = await choXongCao('Đang dò lại');
    if (!v) caoBao('Kiểm tra lâu quá, dừng theo dõi.', 'err');
    else if (v.loi) caoBao('Lỗi: ' + v.loi, 'err');
    else {
      const k = v.ket_qua || {};
      CAO.file = k.file || [];
      veDsCao();
      caoBao(CAO.file.length
        ? 'Có ' + CAO.file.length + ' tài liệu mới — tick rồi bấm nhập.'
        : 'Không có tài liệu mới. Trang vẫn như lần trước.',
        CAO.file.length ? '' : 'info');
      napNguonCao();
    }
  } catch (e) { caoBao('Không kiểm tra được: ' + e.message, 'err'); }
  $('#caoKiemHet').disabled = false;
  $('#caoDo').disabled = false;
}

$('#caoKiemHet').addEventListener('click', () => kiemTraMoi(''));

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
      napKho();
    }
  } catch (e) { caoBao('Không nhập được: ' + e.message, 'err'); }
  $('#caoNhap').disabled = false;
  $('#caoDo').disabled = false;
  capNhatDemCao();
});

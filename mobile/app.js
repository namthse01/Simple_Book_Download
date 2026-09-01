'use strict';
/* DCReader - doc EPUB/TXT offline ngay tren dien thoai.
   Toan bo truyen nam trong IndexedDB cua may; khong goi mang di dau ca. */

const $ = (s) => document.querySelector(s);
const $$ = (s) => Array.from(document.querySelectorAll(s));
const esc = (s) => (s == null ? '' : String(s).replace(/[&<>"]/g,
  (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c])));

/* ================= hộp thoại ================= */
let htTraLoi = null;
function moHopThoai(noiDung, chiBao) {
  $('#htNoiDung').textContent = noiDung;
  $('#htHuy').classList.toggle('hidden', !!chiBao);
  $('#htOk').textContent = chiBao ? 'Đóng' : 'Đồng ý';
  $('#hopThoai').classList.remove('hidden');
  return new Promise((res) => { htTraLoi = res; });
}
function dongHopThoai(ok) {
  $('#hopThoai').classList.add('hidden');
  if (htTraLoi) { htTraLoi(ok); htTraLoi = null; }
}
const hoi = (t) => moHopThoai(t, false);
const nhac = (t) => moHopThoai(t, true);
$('#htOk').addEventListener('click', () => dongHopThoai(true));
$('#htHuy').addEventListener('click', () => dongHopThoai(false));

/* ================= IndexedDB ================= */
let idb = null;
function moDb() {
  return new Promise((res, rej) => {
    const rq = indexedDB.open('dcreader', 1);
    rq.onupgradeneeded = () => {
      const db = rq.result;
      db.createObjectStore('sach', { keyPath: 'id' });   // thong tin + muc luc + vi tri doc
      db.createObjectStore('chuong');                     // key `${id}:${i}` -> {lines}
    };
    rq.onsuccess = () => { idb = rq.result; res(idb); };
    rq.onerror = () => rej(rq.error);
  });
}
function db(store, mode, thao_tac) {
  return new Promise((res, rej) => {
    const tx = idb.transaction(store, mode);
    const rq = thao_tac(tx.objectStore(store));
    tx.oncomplete = () => res(rq && rq.result);
    tx.onerror = () => rej(tx.error);
  });
}
const dsSach = () => db('sach', 'readonly', (s) => s.getAll());
const luuSach = (b) => db('sach', 'readwrite', (s) => s.put(b));
const laySach = (id) => db('sach', 'readonly', (s) => s.get(id));
const luuChuong = (id, i, data) => db('chuong', 'readwrite', (s) => s.put(data, id + ':' + i));
const layChuong = (id, i) => db('chuong', 'readonly', (s) => s.get(id + ':' + i));
async function xoaSachDb(id, soChuong) {
  await db('sach', 'readwrite', (s) => s.delete(id));
  await db('chuong', 'readwrite', (s) => {
    for (let i = 1; i <= soChuong; i++) s.delete(id + ':' + i);
  });
}

/* ================= giải nén ZIP (đọc EPUB, không cần thư viện ngoài) ========= */
async function unzip(buf) {
  const dv = new DataView(buf);
  const u8 = new Uint8Array(buf);
  // tim End Of Central Directory tu cuoi file
  let eocd = -1;
  const cuoi = Math.max(0, buf.byteLength - 22 - 65535);
  for (let i = buf.byteLength - 22; i >= cuoi; i--) {
    if (dv.getUint32(i, true) === 0x06054b50) { eocd = i; break; }
  }
  if (eocd < 0) throw new Error('không phải file ZIP/EPUB hợp lệ');
  const tong = dv.getUint16(eocd + 10, true);
  let off = dv.getUint32(eocd + 16, true);
  const muc = {};
  const td = new TextDecoder();
  for (let n = 0; n < tong; n++) {
    if (dv.getUint32(off, true) !== 0x02014b50) break;
    const method = dv.getUint16(off + 10, true);
    const csize = dv.getUint32(off + 20, true);
    const nlen = dv.getUint16(off + 28, true);
    const elen = dv.getUint16(off + 30, true);
    const clen = dv.getUint16(off + 32, true);
    const lho = dv.getUint32(off + 42, true);
    muc[td.decode(u8.subarray(off + 46, off + 46 + nlen))] = { method, csize, lho };
    off += 46 + nlen + elen + clen;
  }
  async function doc(name) {
    const e = muc[name];
    if (!e) return null;
    const nl = dv.getUint16(e.lho + 26, true);
    const el = dv.getUint16(e.lho + 28, true);
    const dau = e.lho + 30 + nl + el;
    const data = u8.subarray(dau, dau + e.csize);
    if (e.method === 0) return data.slice();
    const ds = new DecompressionStream('deflate-raw');
    const out = await new Response(new Blob([data]).stream().pipeThrough(ds)).arrayBuffer();
    return new Uint8Array(out);
  }
  return { ten: Object.keys(muc), doc };
}

/* ================= chữ: dòng sạch + tách chương TXT ================= */
const chuan = (s) => s.normalize('NFC').replace(/[ \t\r\f\v ​]+/g, ' ').trim();

const HEAD = /^\s*(?:quy[eêể]n\s+\d+\s*[-–—:.]*\s*)?(?:ch[uư][oơ]ng|chapter|h[oôồ]i|ph[aâầ]n|t[aâập]p|m[uụ]c)\s*(?:th[uứ]\s+)?\d+/iu;
const HEAD_CN = /^\s*第\s*[0-9〇零一二三四五六七八九十百千万]+\s*[章节回卷]/u;
const DASHES = /^\s*-{6,}\s*$/;
const PHAN_DAI = 300;                 // khong thay chuong -> tu chia moi phan bay nhieu dong

function laDauChuong(lines, i) {
  const s = lines[i];
  if (!s || s.length > 100) return false;
  if (HEAD.test(s) || HEAD_CN.test(s)) return true;
  return i + 1 < lines.length && DASHES.test(lines[i + 1]) && !DASHES.test(s);
}

function tachTxt(text, tenSach) {
  const lines = text.split('\n').map(chuan).filter(Boolean);
  const heads = [];
  for (let i = 0; i < lines.length; i++) if (laDauChuong(lines, i)) heads.push(i);

  if (heads.length >= 2) {
    const ra = [];
    const dau = lines.slice(0, heads[0]);
    if (dau.length >= 3 || dau.join('').length >= 120) ra.push(['Mở đầu', dau]);
    heads.forEach((h, k) => {
      let body = lines.slice(h + 1, k + 1 < heads.length ? heads[k + 1] : lines.length);
      if (body.length && DASHES.test(body[0])) body = body.slice(1);
      if (body.length) ra.push([lines[h], body]);
    });
    if (ra.length) return ra;
  }
  if (lines.length <= PHAN_DAI * 1.5) return lines.length ? [[tenSach, lines]] : [];
  const ra = [];
  for (let i = 0, n = 1; i < lines.length; i += PHAN_DAI, n++) {
    ra.push(['Phần ' + n, lines.slice(i, i + PHAN_DAI)]);
  }
  return ra;
}

function docText(bytes) {
  // doan bang ma: BOM truoc, roi UTF-8, hong thi thu bang ma Viet/Trung cu
  if (bytes[0] === 0xFF && bytes[1] === 0xFE) return new TextDecoder('utf-16le').decode(bytes);
  if (bytes[0] === 0xFE && bytes[1] === 0xFF) return new TextDecoder('utf-16be').decode(bytes);
  for (const enc of ['utf-8', 'gb18030', 'windows-1258']) {
    try { return new TextDecoder(enc, { fatal: true }).decode(bytes); } catch (e) { /* thu tiep */ }
  }
  return new TextDecoder().decode(bytes);
}

/* ================= EPUB ================= */
function htmlSangDong(docHtml, goc) {
  docHtml.querySelectorAll('script,style,noscript,iframe,nav,header,footer,svg,head')
    .forEach((e) => e.remove());
  const root = goc || docHtml.body || docHtml.documentElement;
  root.querySelectorAll('br').forEach((b) => b.replaceWith('\n'));
  root.querySelectorAll('p,div,h1,h2,h3,h4,li,tr').forEach((t) => t.append('\n'));
  const text = root.textContent || '';
  const DECOR = /^[\s\W_]{0,40}$/u;          // dong chi toan ky tu trang tri
  const out = [];
  for (const raw of text.split('\n')) {
    const s = chuan(raw);
    if (!s || DECOR.test(s)) continue;
    if (out.length && out[out.length - 1] === s) continue;   // dong lap lien tiep
    out.push(s);
  }
  return out;
}

async function nhapEpub(buf, tenFile) {
  const z = await unzip(buf);
  const td = new TextDecoder();
  const parser = new DOMParser();

  const container = td.decode(await z.doc('META-INF/container.xml') || new Uint8Array());
  const mOpf = container.match(/full-path="([^"]+)"/);
  if (!mOpf) throw new Error('EPUB hỏng: không thấy OPF');
  const opfPath = mOpf[1];
  const opfDir = opfPath.includes('/') ? opfPath.slice(0, opfPath.lastIndexOf('/') + 1) : '';
  const opf = parser.parseFromString(td.decode(await z.doc(opfPath)), 'text/xml');

  const the = (tag) => Array.from(opf.getElementsByTagName('*'))
    .filter((e) => e.localName === tag);
  const meta = { title: '', author: '' };
  the('title').forEach((e) => { if (!meta.title) meta.title = chuan(e.textContent || ''); });
  the('creator').forEach((e) => { if (!meta.author) meta.author = chuan(e.textContent || ''); });

  const items = {};
  the('item').forEach((e) => {
    items[e.getAttribute('id')] = {
      href: e.getAttribute('href') || '',
      type: e.getAttribute('media-type') || '',
      props: e.getAttribute('properties') || '',
    };
  });
  const trongZip = (href) => {
    const p = (opfDir + decodeURIComponent(href.split('#')[0]))
      .split('/').reduce((a, x) => {
        if (x === '..') a.pop(); else if (x !== '.' && x !== '') a.push(x);
        return a;
      }, []).join('/');
    return z.ten.includes(p) ? p : null;
  };

  // anh bia
  let coverBlob = null;
  let coverId = '';
  the('meta').forEach((e) => { if (e.getAttribute('name') === 'cover') coverId = e.getAttribute('content') || ''; });
  const ungVien = [coverId, ...Object.keys(items).filter((i) => items[i].props.includes('cover-image'))];
  for (const cid of ungVien) {
    if (!items[cid]) continue;
    const p = trongZip(items[cid].href);
    if (p) {
      const raw = await z.doc(p);
      if (raw && raw.length > 200) {
        coverBlob = new Blob([raw], { type: items[cid].type || 'image/jpeg' });
        break;
      }
    }
  }

  // chuong theo dung thu tu spine
  const chapters = [];
  for (const it of the('itemref')) {
    const item = items[it.getAttribute('idref')];
    if (!item || item.props.split(' ').includes('nav')) continue;
    if (!/html/.test(item.type) && !/\.x?html?$/i.test(item.href)) continue;
    const p = trongZip(item.href);
    if (!p) continue;
    const html = td.decode(await z.doc(p));
    const docHtml = parser.parseFromString(html, 'text/html');
    const h = docHtml.querySelector('h1,h2,h3,h4');
    let title = chuan((h && h.textContent) || (docHtml.querySelector('title') || {}).textContent || '');
    const lines = htmlSangDong(docHtml);
    if (!lines.length) continue;
    if (!title) title = 'Chương ' + (chapters.length + 1);
    while (lines.length && lines[0] === title) lines.shift();
    if (lines.length) chapters.push([title.slice(0, 200), lines]);
  }
  if (!chapters.length) throw new Error('không lấy được chữ nào từ EPUB này');
  return {
    title: meta.title || tenFile.replace(/\.epub$/i, ''),
    author: meta.author, cover: coverBlob, chapters,
  };
}

/* ================= nhập file ================= */
$('#btNhap').addEventListener('click', () => $('#oFile').click());
$('#oFile').addEventListener('change', async () => {
  const files = Array.from($('#oFile').files);
  $('#oFile').value = '';
  if (!files.length) return;
  const bao = $('#baoNhap');
  bao.className = 'notice';
  const loi = [];
  let xong = 0;
  for (const f of files) {
    bao.textContent = `Đang nhập ${f.name}…`;
    try {
      let d;
      if (/\.epub$/i.test(f.name)) d = await nhapEpub(await f.arrayBuffer(), f.name);
      else if (/\.txt$/i.test(f.name)) {
        const text = docText(new Uint8Array(await f.arrayBuffer())).normalize('NFC');
        const ten = f.name.replace(/\.txt$/i, '');
        const chapters = tachTxt(text, ten);
        if (!chapters.length) throw new Error('file rỗng');
        d = { title: ten, author: '', cover: null, chapters };
      } else throw new Error('chỉ nhận .epub hoặc .txt');

      const id = (crypto.randomUUID ? crypto.randomUUID() : String(Date.now() + Math.random()));
      for (let i = 0; i < d.chapters.length; i++) {
        await luuChuong(id, i + 1, { title: d.chapters[i][0], lines: d.chapters[i][1] });
      }
      await luuSach({
        id, title: d.title, author: d.author, cover: d.cover,
        soChuong: d.chapters.length,
        mucLuc: d.chapters.map((c) => c[0]),
        viTri: { chuong: 1, tyLe: 0 },
        them: Date.now(), docLuc: 0,
      });
      xong++;
    } catch (e) { loi.push(f.name + ': ' + e.message); }
  }
  bao.textContent = (xong ? `Đã nhập ${xong} cuốn vào máy.` : '')
    + (loi.length ? '\nLỗi: ' + loi.join('; ') : '');
  bao.className = 'notice' + (loi.length ? ' err' : '');
  if (!xong && !loi.length) bao.classList.add('hidden');
  setTimeout(() => { if (!loi.length) bao.classList.add('hidden'); }, 3500);
  veKho();
});

/* ================= thư viện ================= */
const urlBia = new Map();          // id -> objectURL (giu de khoi tao lai moi lan ve)
function biaCua(b) {
  if (!b.cover) return '';
  if (!urlBia.has(b.id)) urlBia.set(b.id, URL.createObjectURL(b.cover));
  return urlBia.get(b.id);
}

async function veKho() {
  const sach = (await dsSach()).sort((a, b) => (b.docLuc || b.them) - (a.docLuc || a.them));
  $('#khoRong').classList.toggle('hidden', !!sach.length);

  const gan = sach.find((b) => b.docLuc);
  $('#khoDocTiep').innerHTML = gan
    ? `<button class="primary" data-id="${gan.id}">▶ Đọc tiếp: ${esc(gan.title)} · chương ${gan.viTri.chuong}/${gan.soChuong}</button>`
    : '';
  const nutGan = $('#khoDocTiep button');
  if (nutGan) nutGan.addEventListener('click', () => moDoc(gan.id));

  // sach lay tu nguon: dem so chuong da nam trong may de hien "x/y trong máy"
  const daCo = {};
  for (const b of sach) {
    if (b.nguon) daCo[b.id] = (await demChuongCo(b.id)).size;
  }

  $('#dsKho').innerHTML = sach.map((b) => {
    const pct = Math.round(((b.viTri.chuong - 1) / Math.max(1, b.soChuong)) * 100);
    const kho = b.nguon
      ? ` · ${daCo[b.id]}/${b.soChuong} trong máy` : ` · ${b.soChuong} chương`;
    const nutNguon = !b.nguon ? '' : (TAI.id === b.id
      ? `<button class="capnhat" data-dung="1" title="Dừng tải">⏸</button>`
      : (daCo[b.id] < b.soChuong
        ? `<button class="capnhat" data-taihet="${b.id}" title="Tải hết về máy">⬇</button>` : '')
        + `<button class="capnhat" data-capnhat="${b.id}" title="Tìm chương mới">⟳</button>`);
    return `<div class="the" data-id="${b.id}">
      <div class="bia">${b.cover ? `<img src="${biaCua(b)}" alt="">` : '📖'}</div>
      <div class="giua" data-doc="${b.id}">
        <div class="t">${esc(b.title)}</div>
        ${b.author ? `<div class="a">${esc(b.author)}</div>` : ''}
        <div class="s">${b.docLuc ? `Đang ở chương ${b.viTri.chuong}` : 'Chưa đọc'}${kho}</div>
        <div class="tien-trinh"><i style="width:${pct}%"></i></div>
        <div class="dangtai">${TAI.id === b.id ? 'Đang tải về máy…' : ''}</div>
      </div>
      ${nutNguon}
      <button class="xoa" data-xoa="${b.id}" data-ten="${esc(b.title)}">✕</button>
    </div>`;
  }).join('');

  $$('#dsKho [data-doc]').forEach((e) => e.addEventListener('click', () => moDoc(e.dataset.doc)));
  $$('#dsKho [data-taihet]').forEach((e) => e.addEventListener('click', () => {
    taiCaTruyen(e.dataset.taihet);
    veKho();
  }));
  $$('#dsKho [data-capnhat]').forEach((e) => e.addEventListener('click',
    () => capNhatTruyen(e.dataset.capnhat)));
  $$('#dsKho [data-dung]').forEach((e) => e.addEventListener('click', () => { TAI.huy = true; }));
  $$('#dsKho [data-xoa]').forEach((e) => e.addEventListener('click', async () => {
    if (!await hoi(`Xoá "${e.dataset.ten}" khỏi máy?\nKhông hoàn tác được.`)) return;
    if (TAI.id === e.dataset.xoa) TAI.huy = true;
    const b = await laySach(e.dataset.xoa);
    if (b) await xoaSachDb(b.id, b.soChuong);
    veKho();
  }));
}

/* ================= trình đọc ================= */
const DOC = { id: '', sach: null, i: 1 };

async function moDoc(id) {
  const b = await laySach(id);
  if (!b) return;
  DOC.id = id;
  DOC.sach = b;
  $('#rTenTruyen').textContent = b.title;
  veMucLuc();
  kieuDoc();
  $('#rBang').classList.add('hidden');
  $('#rDsChuong').classList.add('hidden');
  $('#docTruyen').classList.remove('hidden');
  await doChuong(b.viTri.chuong || 1, b.viTri.tyLe || 0);
}

function veMucLuc() {
  $('#rDsChuong').innerHTML = DOC.sach.mucLuc
    .map((t, k) => `<button data-i="${k + 1}">${esc(t)}</button>`).join('');
  $$('#rDsChuong button').forEach((el) => el.addEventListener('click', () => {
    $('#rDsChuong').classList.add('hidden');
    doChuong(Number(el.dataset.i), 0);
  }));
}

async function doChuong(i, tyLe) {
  if (i < 1 || i > DOC.sach.soChuong) return;
  const box = $('#rNoiDung');
  let ch = await layChuong(DOC.id, i);
  if (!ch && DOC.sach.nguon) {
    // chua co trong may -> tai truc tiep tu nguon roi cat lai (kieu doc online)
    box.innerHTML = '<div class="khung"><p class="het">Đang tải chương từ nguồn…</p></div>';
    try {
      ch = await taiMotChuong(DOC.sach, i);
    } catch (e) {
      box.innerHTML = '<div class="khung"><p class="het">Không tải được chương này: '
        + esc(e.message) + '<br><br>Không có mạng thì chỉ đọc được phần đã tải về máy.</p></div>';
      return;
    }
  }
  if (!ch) { box.innerHTML = '<div class="khung"><p class="het">Chương này bị thiếu dữ liệu.</p></div>'; return; }
  DOC.i = i;
  const cuoi = i === DOC.sach.soChuong;
  $('#rTenChuong').textContent = ch.title;
  box.innerHTML = '<div class="khung"><h2>' + esc(ch.title) + '</h2>'
    + ch.lines.map((l) => '<p>' + esc(l) + '</p>').join('')
    + (cuoi ? '<p class="het">— Hết truyện —</p>'
      : '<button class="het-nut">Chương sau →</button>')
    + '</div>';
  const nut = box.querySelector('.het-nut');
  if (nut) nut.addEventListener('click', () => doChuong(i + 1, 0));
  box.scrollTop = (tyLe > 0.01 && tyLe < 0.99)
    ? tyLe * (box.scrollHeight - box.clientHeight) : 0;
  capNhatViTri();
  $('#rTruoc').disabled = i === 1;
  $('#rSau').disabled = cuoi;
  $$('#rDsChuong button').forEach((el, k) => el.classList.toggle('on', k + 1 === i));
  const on = $('#rDsChuong button.on');
  if (on) on.scrollIntoView({ block: 'nearest' });
  luuViTri();
}

function tyLeCuon() {
  const nd = $('#rNoiDung');
  const max = nd.scrollHeight - nd.clientHeight;
  return max > 5 ? Math.min(1, nd.scrollTop / max) : 1;
}
function capNhatViTri() {
  $('#rViTri').textContent =
    `Chương ${DOC.i}/${DOC.sach.soChuong} · ${Math.round(tyLeCuon() * 100)}%`;
}
async function luuViTri() {
  if (!DOC.sach) return;
  DOC.sach.viTri = { chuong: DOC.i, tyLe: tyLeCuon() };
  DOC.sach.docLuc = Date.now();
  await luuSach(DOC.sach);
}
let henLuu = 0;
$('#rNoiDung').addEventListener('scroll', () => {
  capNhatViTri();
  clearTimeout(henLuu);
  henLuu = setTimeout(luuViTri, 400);
});

/* chạm giữa màn hình = hiện/ẩn thanh công cụ (đọc chìm như app truyện) */
let chimTimer = 0;
$('#rNoiDung').addEventListener('click', (e) => {
  if (e.target.closest('button')) return;
  if (!$('#rBang').classList.contains('hidden')) { $('#rBang').classList.add('hidden'); return; }
  if (!$('#rDsChuong').classList.contains('hidden')) { $('#rDsChuong').classList.add('hidden'); return; }
  $('.reader-top').classList.toggle('an');
  $('.reader-nav').classList.toggle('an');
});

/* ---- kiểu đọc ---- */
const KIEU_MAC_DINH = { co: 18, phong: 'sans', gian: '1.85', nen: 'toi' };
function docKieu() {
  try { return { ...KIEU_MAC_DINH, ...(JSON.parse(localStorage.getItem('kieu') || 'null') || {}) }; }
  catch (e) { return { ...KIEU_MAC_DINH }; }
}
function doiKieu(key, val) {
  const k = docKieu();
  k[key] = val;
  try { localStorage.setItem('kieu', JSON.stringify(k)); } catch (e) { /**/ }
  kieuDoc();
}
function kieuDoc() {
  const k = docKieu();
  const nd = $('#rNoiDung');
  nd.style.setProperty('--co-chu', k.co + 'px');
  nd.style.setProperty('--gian-doc', k.gian);
  nd.style.setProperty('--font-doc', k.phong === 'serif'
    ? "Georgia,'Times New Roman',serif" : "'Segoe UI',system-ui,Roboto,sans-serif");
  $('#docTruyen').classList.toggle('giay', k.nen === 'giay');
  $('#docTruyen').classList.toggle('den', k.nen === 'den');
  $('#rCoChu').textContent = k.co;
  [['#rPhong', k.phong], ['#rGian', k.gian], ['#rNenOps', k.nen]]
    .forEach(([sel, val]) => $$(sel + ' button')
      .forEach((b) => b.classList.toggle('on', b.dataset.v === String(val))));
}
$('#rAa').addEventListener('click', () => $('#rBang').classList.toggle('hidden'));
$('#rNho').addEventListener('click', () => doiKieu('co', Math.max(13, docKieu().co - 1)));
$('#rTo').addEventListener('click', () => doiKieu('co', Math.min(34, docKieu().co + 1)));
[['#rPhong', 'phong'], ['#rGian', 'gian'], ['#rNenOps', 'nen']]
  .forEach(([sel, key]) => $$(sel + ' button')
    .forEach((b) => b.addEventListener('click', () => doiKieu(key, b.dataset.v))));

$('#rDong').addEventListener('click', async () => {
  await luuViTri();
  $('#docTruyen').classList.add('hidden');
  $('.reader-top').classList.remove('an');
  $('.reader-nav').classList.remove('an');
  veKho();
});
$('#rTruoc').addEventListener('click', () => doChuong(DOC.i - 1, 0));
$('#rSau').addEventListener('click', () => doChuong(DOC.i + 1, 0));
$('#rMucLuc').addEventListener('click', () => $('#rDsChuong').classList.toggle('hidden'));

document.addEventListener('keydown', (e) => {
  if ($('#docTruyen').classList.contains('hidden')) return;
  if (e.key === 'ArrowLeft') doChuong(DOC.i - 1, 0);
  else if (e.key === 'ArrowRight') doChuong(DOC.i + 1, 0);
  else if (e.key === 'Escape') $('#rDong').click();
});

/* ================= nguồn truyện: BLHVIP ================= */
/* Trong APK, Capacitor chuyen fetch() qua lop native nen goi thang web nguon
   duoc, khong vuong CORS. Khi thu tren trinh duyet may tinh thi mo trang voi
   ?proxy=http://.../?u= de di vong qua mot proxy nho. */
const PROXY = new URLSearchParams(location.search).get('proxy') || '';
const API_BLH = 'https://api.blhvip.vn';
const SITE_BLH = 'https://blhvip.vn';

async function taiVe(url, kieu) {
  const u = PROXY ? PROXY + encodeURIComponent(url) : url;
  const r = await fetch(u, {
    headers: { Referer: SITE_BLH + '/', 'User-Agent': 'Mozilla/5.0 (Linux; Android 13)' },
  });
  if (!r.ok) throw new Error('HTTP ' + r.status);
  if (kieu === 'json') return r.json();
  if (kieu === 'blob') return r.blob();
  return r.text();
}

const blhSlug = (url) => {
  const m = String(url).match(/\/truyen\/([^/?#]+)/);
  return m ? m[1] : '';
};

async function blhTim(tuKhoa) {
  const d = await taiVe(`${API_BLH}/v1/search?keyword=${encodeURIComponent(tuKhoa)}&page=1`, 'json');
  return (d.data || []).filter((x) => x.slug).map((x) => ({
    ten: x.name || x.slug, slug: x.slug, tacGia: x.author_name || '',
    bia: x.img_url || '', soChuong: x.chapter_count || 0,
    trangThai: x.status || '', moTa: x.content || '',
  }));
}

async function blhMucLuc(slug, baoTienDo) {
  const trang = async (n) => {
    const d = await taiVe(`${API_BLH}/v1/story/${slug}/chapter_list?page=${n}&new=0`, 'json');
    return d;
  };
  const dau = await trang(1);
  let rows = dau.data || [];
  const tong = Math.min(Number(dau.total_page) || 1, 400);
  for (let n = 2; n <= tong; n += 4) {
    // 4 trang mot dot cho nhanh ma khong doi web
    const batch = [];
    for (let k = n; k < Math.min(n + 4, tong + 1); k++) batch.push(trang(k));
    for (const d of await Promise.all(batch)) rows = rows.concat(d.data || []);
    if (baoTienDo) baoTienDo(Math.min(n + 3, tong), tong);
  }
  const ra = [];
  const seen = new Set();
  for (const it of rows) {
    let href = it.url || '';
    if (!href) continue;
    if (!href.startsWith('http')) href = SITE_BLH + href;
    if (seen.has(href)) continue;
    seen.add(href);
    ra.push({ ten: chuan(it.name || `Chương ${ra.length + 1}`), url: href });
  }
  return ra;
}

async function blhNoiDung(url) {
  const html = await taiVe(url, 'text');
  const doc = new DOMParser().parseFromString(html, 'text/html');
  const body = doc.querySelector('#chapter-content .s-content')
    || doc.querySelector('.s-content')
    || doc.querySelector('#chapter-content')
    || doc.querySelector('.chapter-content');
  if (!body) throw new Error('không thấy khung nội dung chương');
  body.querySelectorAll("script,style,ins,iframe,[class*='ads'],.ads,"
    + 'h1.chapter-title,p.info-detail,.chapter-nav').forEach((e) => e.remove());
  if ((body.textContent || '').trim().length < 200) {
    throw new Error('chương bị khoá hoặc rỗng');
  }
  return htmlSangDong(doc, body);
}

/* ================= registry nguồn ================= */
const NGUON = {};        // id -> {id, ten, home, list, search, detail, toc, chap}

// ---- BLHVIP: adapter viết tay (API riêng của trang) ----
function blhParseList(html) {
  const doc = new DOMParser().parseFromString(html, 'text/html');
  const laTenXau = (s) => !s || s === 'FULL' || /\.(jpe?g|png|webp|gif)$/i.test(s);
  const seen = new Map();
  doc.querySelectorAll('a[href]').forEach((a) => {
    const m = (a.getAttribute('href') || '').match(/^(?:https:\/\/blhvip\.vn\/|\/)?truyen\/([a-z0-9-]+)\/?$/);
    if (!m) return;
    const img = a.querySelector('img');
    // uu tien title cua the a, roi chu trong the, cuoi cung moi den alt anh
    // (alt tren trang chu blhvip la TEN FILE anh, khong dung duoc)
    let ten = '';
    for (const uv of [a.getAttribute('title'), a.textContent,
      img && img.getAttribute('alt')]) {
      const s = chuan(uv || '');
      if (!laTenXau(s)) { ten = s; break; }
    }
    let bia = '';
    if (img) {
      for (const uv of [img.getAttribute('src'), img.getAttribute('data-src'),
        img.getAttribute('data-original')]) {
        if (uv && !uv.startsWith('data:')) { bia = uv; break; }
      }
    }
    const cu = seen.get(m[1]) || { ten: '', bia: '' };
    seen.set(m[1], { ten: cu.ten || ten, bia: cu.bia || bia });
  });
  return [...seen.entries()]
    .filter(([, v]) => v.ten)
    .map(([slug, v]) => ({ ten: v.ten, link: `${SITE_BLH}/truyen/${slug}`, bia: v.bia, moTa: '' }));
}

NGUON.blhvip = {
  id: 'blhvip',
  ten: 'BLHVIP',
  home: async () => [
    { title: 'Đề cử', script: '', input: '' },
    { title: 'Truyện hot', script: '', input: 'truyen-hot' },
    { title: 'Mới nhất', script: '', input: 'truyen-moi-nhat' },
    { title: 'Hoàn thành', script: '', input: 'truyen-hoan-thanh' },
    { title: 'Thịnh hành tuần', script: '', input: 'truyen-thinh-hanh-trong-tuan' },
  ],
  list: async (script, input) => ({
    items: blhParseList(await taiVe(SITE_BLH + '/' + (input || ''), 'text')),
    next: '',
  }),
  search: async (kw) => ({
    items: (await blhTim(kw)).map((x) => ({
      ten: x.ten, link: `${SITE_BLH}/truyen/${x.slug}`, bia: x.bia,
      moTa: [x.tacGia, x.soChuong ? x.soChuong + ' chương' : ''].filter(Boolean).join(' · '),
    })),
    next: '',
  }),
  detail: async (link) => {
    const doc = new DOMParser().parseFromString(await taiVe(link, 'text'), 'text/html');
    let ten = chuan((doc.querySelector('title') || {}).textContent || '');
    ten = ten.replace(/^\s*\[[^\]]{1,20}\]\s*/, '') || chuan((doc.querySelector('h1') || {}).textContent || '');
    const og = doc.querySelector("meta[property='og:image']");
    const au = doc.querySelector("a[href*='tac-gia']");
    let trangThai = '';
    doc.querySelectorAll('p.text-info, .text-info').forEach((p) => {
      const t = chuan(p.textContent);
      if (!trangThai && /^(tình trạng|trạng thái)\s*:/i.test(t)) trangThai = t.split(':')[1] || '';
    });
    const mota = doc.querySelector('.s-content, .tabcontent');
    return {
      ten, tacGia: au ? chuan(au.textContent) : '',
      bia: og ? (og.getAttribute('content') || '') : '',
      trangThai: chuan(trangThai), moTa: mota ? chuan(mota.textContent) : '',
    };
  },
  toc: async (link) => blhMucLuc(blhSlug(link)),
  chap: async (url) => blhNoiDung(url),
};

// ---- Các nguồn VBook: chạy qua lớp giả lập vbook.js ----
function nguonTuExt(ext) {
  ext.__mapSearch = (ext.map && ext.map.search) || 'search.js';
  const chuanItems = (list) => (list || []).map((x) => ({
    ten: chuan(x.name || ''),
    link: VB.tuyetDoi(x.link || '', x.host || ext.nguon),
    bia: VB.tuyetDoi(x.cover || '', x.host || ext.nguon),
    moTa: chuan(String(x.description || '').replace(/<[^>]+>/g, ' ')),
  })).filter((x) => x.ten && x.link);
  return {
    id: ext.id,
    ten: ext.ten,
    home: async () => ((await VB.chay(ext, (ext.map && ext.map.home) || 'home.js', [])).data || [])
      .map((t) => ({ title: t.title, script: (t.script || '').split('/').pop(), input: t.input || '' })),
    list: async (script, input, page) => {
      const kq = await VB.chay(ext, script, [input, page || '']);
      return { items: chuanItems(kq.data), next: kq.data2 || '' };
    },
    search: async (kw, page) => {
      const kq = await VB.chay(ext, ext.__mapSearch, [kw, page || '']);
      return { items: chuanItems(kq.data), next: kq.data2 || '' };
    },
    detail: async (link) => {
      const d = (await VB.chay(ext, (ext.map && ext.map.detail) || 'detail.js', [link])).data || {};
      return {
        ten: chuan(d.name || ''), tacGia: chuan(d.author || ''),
        bia: VB.tuyetDoi(d.cover || '', d.host || ext.nguon),
        trangThai: d.ongoing === false ? 'Hoàn thành' : (d.ongoing === true ? 'Đang ra' : ''),
        moTa: chuan(String(d.description || '').replace(/<br\s*\/?>/gi, '\n').replace(/<[^>]+>/g, ' ')),
      };
    },
    toc: async (link) => ((await VB.chay(ext, (ext.map && ext.map.toc) || 'toc.js', [link])).data || [])
      .map((c) => ({ ten: chuan(c.name || ''), url: VB.tuyetDoi(c.url || '', c.host || ext.nguon) }))
      .filter((c) => c.url),
    chap: async (url) => {
      const kq = await VB.chay(ext, (ext.map && ext.map.chap) || 'chap.js', [url]);
      const html = String(kq.data == null ? '' : kq.data);
      const doc = new DOMParser().parseFromString('<div id="__c">' + html + '</div>', 'text/html');
      const lines = htmlSangDong(doc, doc.getElementById('__c'));
      if (!lines.length) throw new Error('chương rỗng (web đổi giao diện?)');
      return lines;
    },
  };
}
(window.NGUON_VBOOK || []).forEach((ext) => { NGUON[ext.id] = nguonTuExt(ext); });

/* ---- Nguồn chung: bộ dò tự đoán cấu trúc trang — đặc sản nhà trồng.
   Port từ plugins/generic.py của bản PC: dán link trang truyện bất kỳ,
   app tự tìm khối danh sách chương (chấm điểm theo mật độ link chương),
   tự suy ra kiểu đánh số trang, tự đoán khung nội dung (nhiều chữ ít link). */
const G_CHAP_TEXT = /^\s*(ch[uư][oơ]ng|chapter|chuong|h[oồ]i|t[aậ]p|quy[eể]n|ch\.)\s*[:.\-]?\s*\d+/iu;
const G_CHAP_HREF = /(chuong|chapter|\/c\d+([./-]|$)|\/ch\d+|episode|\/p\d+\.html)/i;
const G_PAGE_HREF = /(trang[-=/](\d+)|[?&]page=(\d+)|\/page\/(\d+))/i;
const G_JUNK = "script,style,ins,iframe,noscript,nav,header,footer,form,button,"
  + ".ads,[class*='ads'],[id*='ads'],.quangcao,.share,.social,.comment,.comments,"
  + ".pagination,.breadcrumb";

async function gDoc(url) {
  const r = await VB.fetch(url);
  if (!r.ok) throw new Error('HTTP ' + r.status);
  return { doc: new DOMParser().parseFromString(r.text(), 'text/html'), url: r.url || url };
}
const gMeta = (doc, prop) => {
  const el = doc.querySelector(`meta[property='${prop}'], meta[name='${prop}']`);
  return el ? chuan(el.getAttribute('content') || '') : '';
};
const gHost = (u) => { try { return new URL(u).host; } catch (e) { return ''; } };
const gNoi = (base, href) => { try { return new URL(href, base).href; } catch (e) { return ''; } };

function gPageLinks(base, doc) {
  const host = gHost(base);
  const out = [];
  doc.querySelectorAll("[class*='pag'] a[href], [id*='pag'] a[href]").forEach((a) => {
    const full = gNoi(base, a.getAttribute('href') || '');
    if (full && gHost(full) === host && G_PAGE_HREF.test(full)) out.push(full.split('#')[0]);
  });
  return [...new Set(out)];
}

function gLinksOf(base, doc) {
  // gom link chuong roi cham diem khoi cha: khoi danh sach chuong that co
  // NHIEU link chuong va ty le link-chuong/tong-link cao
  const host = gHost(base);
  const found = [];
  doc.querySelectorAll('a[href]').forEach((a) => {
    const href = a.getAttribute('href') || '';
    if (!href || /^(#|javascript:|mailto:)/.test(href)) return;
    const full = gNoi(base, href);
    if (!full || gHost(full) !== host) return;
    const name = chuan(a.getAttribute('title') || a.textContent || '');
    if (G_CHAP_TEXT.test(name) || G_CHAP_HREF.test(full.split('#')[0])) {
      found.push([a, full, name]);
    }
  });
  if (!found.length) return [];

  const diem = new Map();               // element -> so link chuong ben trong
  for (const [a] of found) {
    let el = a.parentElement;
    for (let i = 0; i < 6 && el && el !== doc.documentElement; i++) {
      diem.set(el, (diem.get(el) || 0) + 1);
      el = el.parentElement;
    }
  }
  let best = null;
  let bestScore = -1;
  for (const [el, nChap] of diem) {
    const nAll = Math.max(1, el.querySelectorAll('a[href]').length);
    const score = (nChap * nChap) / nAll;
    if (score > bestScore) { best = el; bestScore = score; }
  }
  const out = [];
  const seen = new Set();
  for (const [a, full, name] of found) {
    if (best && !best.contains(a)) continue;
    if (!seen.has(full)) { seen.add(full); out.push([full, name]); }
  }
  return out;
}

function gPagePattern(base, doc) {
  let tmpl = '';
  let maxPage = 1;
  for (const link of gPageLinks(base, doc)) {
    const m = G_PAGE_HREF.exec(link);
    if (!m) continue;
    const digits = /\d+/.exec(m[0]);
    if (!digits) continue;
    maxPage = Math.max(maxPage, Number(digits[0]));
    if (!tmpl) {
      const seg = m[0].replace(digits[0], '\x00');
      tmpl = link.slice(0, m.index) + seg + link.slice(m.index + m[0].length);
    }
  }
  return [tmpl, Math.min(maxPage, 400)];
}

NGUON.chung = {
  id: 'chung',
  ten: 'Nguồn chung (dán link)',
  an: true,                              // khong hien trong chips — chi kich hoat khi dan link
  home: async () => [],
  list: async () => ({ items: [], next: '' }),
  search: async () => { throw new Error('nguồn chung chỉ nhận link dán thẳng'); },
  detail: async (url) => {
    const { doc } = await gDoc(url);
    let ten = chuan((doc.querySelector('h1') || {}).textContent || '')
      || chuan((doc.querySelector('title') || {}).textContent || '')
      || gMeta(doc, 'og:title') || 'Truyện';
    ten = ten.replace(/^\s*\[[^\]]{1,20}\]\s*/, '').replace(/\s*[-|–]\s*[^-|–]{0,40}$/, '').trim() || 'Truyện';
    let moTa = gMeta(doc, 'og:description') || gMeta(doc, 'description');
    if (moTa && moTa === gMeta(doc, 'og:title')) moTa = '';
    let tacGia = '';
    for (const q of ["[itemprop='author']", "[class*='author']", "[rel='author']"]) {
      const el = doc.querySelector(q);
      if (el) { tacGia = chuan(el.textContent).slice(0, 120); break; }
    }
    return { ten, tacGia, bia: gNoi(url, gMeta(doc, 'og:image')), trangThai: '', moTa };
  },
  toc: async (url) => {
    const dau = await gDoc(url);
    const pages = [dau.doc];
    const [tmpl, maxPage] = gPagePattern(url, dau.doc);
    if (tmpl && maxPage > 1) {
      // danh sach chuong danh so trang ro rang -> doc thang trang 2..N, 5 trang/dot
      for (let n = 2; n <= maxPage; n += 5) {
        const dot = [];
        for (let k = n; k < Math.min(n + 5, maxPage + 1); k++) {
          dot.push(gDoc(tmpl.replace('\x00', String(k))).then((r) => r.doc).catch(() => null));
        }
        for (const d of await Promise.all(dot)) if (d) pages.push(d);
      }
    } else {
      // khong doan duoc -> do lan theo link phan trang
      const daTham = new Set([url.split('#')[0]]);
      const cho = gPageLinks(url, dau.doc).filter((p) => !daTham.has(p));
      while (cho.length && daTham.size < 300) {
        const p = cho.shift();
        if (daTham.has(p)) continue;
        daTham.add(p);
        try {
          const { doc } = await gDoc(p);
          pages.push(doc);
          for (const q of gPageLinks(url, doc)) if (!daTham.has(q)) cho.push(q);
        } catch (e) { /* trang hong thi bo qua */ }
      }
    }
    const seen = new Map();
    for (const doc of pages) {
      for (const [href, name] of gLinksOf(url, doc)) {
        if (!seen.has(href)) seen.set(href, name);
      }
    }
    return [...seen.entries()].map(([u, t], i) => ({ ten: t || `Chương ${i + 1}`, url: u }));
  },
  chap: async (url) => {
    const { doc } = await gDoc(url);
    doc.querySelectorAll(G_JUNK).forEach((e) => e.remove());
    let khung = null;
    for (const q of ['#chapter-c', '.chapter-c', '#chapter-content', '.chapter-content',
      '#content', '.content-chapter', '#chr-content', '.reading-content',
      'article .entry-content', "[itemprop='articleBody']"]) {
      const el = doc.querySelector(q);
      if (el && chuan(el.textContent).length > 200) { khung = el; break; }
    }
    if (!khung) {
      // cham diem: nhieu chu, it link, nhieu doan
      let bestScore = 0;
      doc.querySelectorAll('div, article, section, td').forEach((el) => {
        const n = chuan(el.textContent).length;
        if (n < 300) return;
        let linkLen = 0;
        el.querySelectorAll('a').forEach((a) => { linkLen += chuan(a.textContent).length; });
        const breaks = el.querySelectorAll('p, br').length;
        let sau = 0;
        for (let p = el; p; p = p.parentElement) sau++;
        const score = n - 4 * linkLen + 12 * breaks + sau * 5;
        if (score > bestScore) { khung = el; bestScore = score; }
      });
    }
    if (!khung) throw new Error('không đoán được khung nội dung ở trang này');
    const lines = htmlSangDong(doc, khung);
    if (!lines.length) throw new Error('chương rỗng');
    return lines;
  },
};

const nguonCua = (b) => {
  // sach cu luu {loai:'blhvip', slug} -> quy ve dang moi
  if (b.nguon && !b.nguon.ext && b.nguon.loai === 'blhvip') {
    b.nguon = { ext: 'blhvip', url: b.nguon.url || `${SITE_BLH}/truyen/${b.nguon.slug}` };
  }
  return b.nguon && b.nguon.ext ? NGUON[b.nguon.ext] : null;
};

/* ---------- màn khám phá ---------- */
let CT = null;                    // {nguon, link, ten, tacGia, bia, moTa, trangThai, soChuong}
const TIM = { nguon: '', script: '', input: '', page: '', next: '', tuKhoa: '', items: [] };

$('#btTim').addEventListener('click', () => {
  $('#manTim').classList.remove('hidden');
  if (!TIM.nguon) chonNguon(Object.keys(NGUON)[0]);
});
$('#tDong').addEventListener('click', () => $('#manTim').classList.add('hidden'));
$('#tTim').addEventListener('click', () => timNguon());
$('#tTuKhoa').addEventListener('keydown', (e) => { if (e.key === 'Enter') timNguon(); });

function baoTim(msg, err) {
  const el = $('#tBao');
  el.textContent = msg;
  el.className = 'notice' + (err ? ' err' : '');
  el.classList.toggle('hidden', !msg);
}

function veNguonChips() {
  $('#tNguon').innerHTML = Object.values(NGUON).filter((n) => !n.an).map((n) =>
    `<button data-n="${n.id}" class="${n.id === TIM.nguon ? 'on' : ''}">${esc(n.ten)}</button>`).join('');
  $$('#tNguon button').forEach((b) => b.addEventListener('click', () => chonNguon(b.dataset.n)));
}

async function chonNguon(id) {
  TIM.nguon = id;
  TIM.tuKhoa = '';
  $('#tTuKhoa').value = '';
  $('#tChiTiet').classList.add('hidden');
  veNguonChips();
  $('#tTab').innerHTML = '';
  $('#tKetQua').innerHTML = '';
  $('#tThem').classList.add('hidden');
  baoTim('Đang lấy các mục của nguồn…');
  try {
    const tabs = await NGUON[id].home();
    baoTim('');
    $('#tTab').innerHTML = tabs.map((t, i) =>
      `<button data-i="${i}">${esc(t.title)}</button>`).join('');
    $$('#tTab button').forEach((b) => b.addEventListener('click', () => {
      $$('#tTab button').forEach((x) => x.classList.remove('on'));
      b.classList.add('on');
      const t = tabs[Number(b.dataset.i)];
      moTab(t.script, t.input);
    }));
    if (tabs.length) $('#tTab button').click();
  } catch (e) { baoTim('Nguồn này đang lỗi: ' + e.message, true); }
}

async function moTab(script, input) {
  TIM.script = script;
  TIM.input = input;
  TIM.tuKhoa = '';
  TIM.page = '';
  TIM.items = [];
  await napTrang(true);
}

async function timNguon() {
  const kw = $('#tTuKhoa').value.trim();
  if (!kw) return;
  $('#tChiTiet').classList.add('hidden');
  if (/^https?:\/\//i.test(kw)) return moChiTietLink(kw);
  $$('#tTab button').forEach((x) => x.classList.remove('on'));
  TIM.tuKhoa = kw;
  TIM.page = '';
  TIM.items = [];
  await napTrang(true);
}

async function napTrang(moi) {
  const n = NGUON[TIM.nguon];
  if (!n) return;
  baoTim(moi ? 'Đang tải danh sách…' : '');
  $('#tThem').disabled = true;
  try {
    const kq = TIM.tuKhoa
      ? await n.search(TIM.tuKhoa, TIM.page)
      : await n.list(TIM.script, TIM.input, TIM.page);
    TIM.items = moi ? kq.items : TIM.items.concat(kq.items);
    TIM.next = kq.next || '';
    TIM.page = TIM.next;
    baoTim(TIM.items.length ? '' : 'Không có truyện nào ở mục này.');
    veKetQua();
  } catch (e) { baoTim('Lỗi: ' + e.message, true); }
  $('#tThem').disabled = false;
}

function veKetQua() {
  $('#tKetQua').innerHTML = TIM.items.map((x, i) => `
    <div class="the" data-i="${i}">
      <div class="bia">${x.bia ? `<img loading="lazy" src="${esc(x.bia)}" alt="" onerror="this.remove()">` : '📖'}</div>
      <div class="giua">
        <div class="t">${esc(x.ten)}</div>
        <div class="a">${esc(x.moTa || '')}</div>
      </div>
    </div>`).join('');
  $$('#tKetQua .the').forEach((el) => el.addEventListener('click',
    () => moChiTietLink(TIM.items[Number(el.dataset.i)].link)));
  $('#tThem').classList.toggle('hidden', !TIM.next);
}

$('#tThem').addEventListener('click', () => napTrang(false));

async function moChiTietLink(link) {
  // dan link: nguon nao nhan ra thi dung nguon do, khong thi BO DO TU DOAN lo
  let id = '';
  for (const ext of (window.NGUON_VBOOK || [])) {
    try { if (ext.regexp && new RegExp(ext.regexp).test(link)) { id = ext.id; break; } } catch (e) { /**/ }
  }
  if (/blhvip\.vn/.test(link)) id = 'blhvip';
  if (!id) id = 'chung';
  baoTim('Đang đọc trang truyện…' + (id === 'chung' ? ' (bộ dò tự đoán cấu trúc)' : ''));
  try {
    const d = await NGUON[id].detail(link);
    if (!d.ten) throw new Error('không đọc được trang này');
    CT = { nguon: id, link, ...d };
    baoTim('');
    veChiTiet();
  } catch (e) { baoTim('Lỗi: ' + e.message, true); }
}

function veChiTiet() {
  $('#ctTen').textContent = CT.ten;
  $('#ctTacGia').textContent = CT.tacGia ? 'Tác giả: ' + CT.tacGia : '';
  $('#ctTrangThai').textContent = [NGUON[CT.nguon].ten, CT.trangThai].filter(Boolean).join(' · ');
  $('#ctSoChuong').textContent = CT.soChuong ? CT.soChuong + ' chương' : '';
  $('#ctMoTa').textContent = CT.moTa || '';
  const img = $('#ctBia');
  img.src = CT.bia || '';
  img.style.display = CT.bia ? '' : 'none';
  $('#tChiTiet').classList.remove('hidden');
  $('#tChiTiet').scrollIntoView({ behavior: 'smooth', block: 'start' });
}

/* ---------- thêm vào tủ ---------- */
async function themVaoTu() {
  // da co trong tu roi thi dung lai cuon do
  const cu = (await dsSach()).find((b) => b.nguon && (b.nguon.url === CT.link
    || (b.nguon.slug && CT.link.includes('/' + b.nguon.slug))));
  if (cu) return cu;

  baoTim('Đang lấy mục lục… (truyện dài mất chút xíu)');
  const ml = await NGUON[CT.nguon].toc(CT.link);
  if (!ml.length) throw new Error('không lấy được chương nào');
  // nhieu trang ghi ten chuong kieu "Ten Truyen - Chuong 5" -> cat tien to di
  if (CT.ten) {
    const tienTo = new RegExp('^' + CT.ten.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + '\\s*[-–—:]\\s*', 'i');
    ml.forEach((c) => { c.ten = c.ten.replace(tienTo, ''); });
  }
  let cover = null;
  if (CT.bia) {
    try {
      const r = await fetch(PROXY ? PROXY + encodeURIComponent(CT.bia) : CT.bia);
      if (r.ok) cover = await r.blob();
    } catch (e) { /* khong co bia cung chang sao */ }
  }
  const b = {
    id: (crypto.randomUUID ? crypto.randomUUID() : String(Date.now())),
    title: CT.ten, author: CT.tacGia, cover,
    soChuong: ml.length, mucLuc: ml.map((c) => c.ten),
    dsUrl: ml.map((c) => c.url),
    nguon: { ext: CT.nguon, url: CT.link },
    daTai: 0, viTri: { chuong: 1, tyLe: 0 }, them: Date.now(), docLuc: 0,
  };
  await luuSach(b);
  baoTim('');
  return b;
}

$('#ctDoc').addEventListener('click', async () => {
  $('#ctDoc').disabled = true;
  try {
    const b = await themVaoTu();
    $('#manTim').classList.add('hidden');
    veKho();
    moDoc(b.id);
  } catch (e) { baoTim('Lỗi: ' + e.message, true); }
  $('#ctDoc').disabled = false;
});

$('#ctTaiHet').addEventListener('click', async () => {
  $('#ctTaiHet').disabled = true;
  try {
    const b = await themVaoTu();
    $('#manTim').classList.add('hidden');
    veKho();
    taiCaTruyen(b.id);
  } catch (e) { baoTim('Lỗi: ' + e.message, true); }
  $('#ctTaiHet').disabled = false;
});

/* ---------- tải một chương / cả truyện ---------- */
async function taiMotChuong(b, i) {
  const n = nguonCua(b);
  if (!n) throw new Error('không rõ nguồn của truyện này');
  const lines = await n.chap(b.dsUrl[i - 1]);
  const title = b.mucLuc[i - 1] || `Chương ${i}`;
  const bo = [...lines];
  while (bo.length && bo[0] === title) bo.shift();
  await luuChuong(b.id, i, { title, lines: bo.length ? bo : lines });
  return { title, lines: bo.length ? bo : lines };
}

async function demChuongCo(id) {
  const keys = await db('chuong', 'readonly',
    (s) => s.getAllKeys(IDBKeyRange.bound(id + ':', id + ';')));
  return new Set((keys || []).map((k) => Number(k.split(':').pop())));
}

const TAI = { id: '', huy: false };

async function taiCaTruyen(id) {
  if (TAI.id) { await nhac('Đang tải cuốn khác — đợi xong hoặc bấm Dừng đã.'); return; }
  TAI.id = id;
  TAI.huy = false;
  const b = await laySach(id);
  if (!b || !b.nguon) { TAI.id = ''; return; }
  const co = await demChuongCo(id);
  let loi = 0;
  const capNhatThe = () => {
    const el = document.querySelector(`.the[data-id="${id}"] .dangtai`);
    if (el) {
      el.textContent = `Đang tải về máy: ${co.size}/${b.soChuong}`
        + (loi ? ` · ${loi} chương lỗi` : '') + ' — bấm ⏸ để dừng';
    }
  };
  const mot = async (i) => {
    if (TAI.huy || co.has(i)) return;
    try {
      await taiMotChuong(b, i);
      co.add(i);
    } catch (e) { loi++; }
  };
  // 3 luong mot luc, du nhanh ma khong lam web kho chiu
  let ke = 1;
  const tho = async () => {
    while (ke <= b.soChuong && !TAI.huy) {
      const i = ke++;
      await mot(i);
      if (i % 5 === 0) capNhatThe();
      await new Promise((r) => setTimeout(r, 120));
    }
  };
  await Promise.all([tho(), tho(), tho()]);
  b.daTai = co.size;
  await luuSach(b);
  TAI.id = '';
  veKho();
  if (!TAI.huy && loi) nhac(`Xong nhưng có ${loi} chương lỗi — bấm tải lại để thử tiếp phần thiếu.`);
}

/* ---------- cập nhật chương mới ---------- */
async function capNhatTruyen(id) {
  const b = await laySach(id);
  if (!b || !b.nguon) return;
  const nut = document.querySelector(`.the[data-id="${id}"] .capnhat`);
  if (nut) nut.textContent = '…';
  try {
    const n = nguonCua(b);
    if (!n) throw new Error('không rõ nguồn của truyện này');
    const ml = await n.toc(b.nguon.url);
    const moi = ml.length - b.dsUrl.length;
    if (moi > 0) {
      b.dsUrl = ml.map((c) => c.url);
      b.mucLuc = ml.map((c) => c.ten);
      b.soChuong = ml.length;
      await luuSach(b);
      await nhac(`Có ${moi} chương mới! Tổng ${ml.length} chương.\nMở đọc là chương mới tự tải, hoặc bấm nút tải để cất hết vào máy.`);
    } else {
      await nhac(`Đã mới nhất — nguồn cũng chỉ có ${ml.length} chương.`);
    }
    veKho();
  } catch (e) { nhac('Không kiểm tra được: ' + e.message); }
}

/* ================= khởi động ================= */
if ('serviceWorker' in navigator) {
  navigator.serviceWorker.register('sw.js').catch(() => { /* mo tu file:// thi thoi */ });
}
moDb().then(veKho).catch((e) => {
  $('#khoRong').textContent = 'Không mở được kho lưu của trình duyệt: ' + e;
});

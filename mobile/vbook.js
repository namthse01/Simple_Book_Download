/* Lop gia lap moi truong extension VBook cho DCReader.
   Extension VBook la JS dong bo kieu Jsoup (fetch().html().select()...).
   O day: fetch da duoc chuyen thanh async tu buoc dong goi, con DOM thi
   boc DOMParser cua trinh duyet sao cho giong Jsoup (text/attr rong thay
   vi crash, attr("abs:href"), select tren tap phan tu...). KHONG strict
   mode vi executor dung with(). */

window.VB = (function () {
  var UA = 'Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 Chrome/126 Mobile Safari/537.36';
  var PROXY = '';
  try { PROXY = new URLSearchParams(location.search).get('proxy') || ''; } catch (e) { }

  var __phanTuRong = null;
  function rong() {
    if (!__phanTuRong) __phanTuRong = document.createElement('div');
    return __phanTuRong;
  }

  var gọn = function (s) { return String(s == null ? '' : s).replace(/\s+/g, ' ').trim(); };

  // Jsoup cho phep [attr=gia tri khong ngoac kep] — CSS thi khong
  function suaSelector(q) {
    return String(q).replace(/\[\s*([\w-]+)\s*=\s*([^\]"'][^\]]*)\]/g,
      function (m, a, v) { return '[' + a + '="' + v.trim().replace(/"/g, '\\"') + '"]'; });
  }
  function chon(node, q) {
    try { return Array.from(node.querySelectorAll(suaSelector(q))); } catch (e) { return []; }
  }
  function tuyetDoi(v, base) {
    if (!v) return '';
    try { return new URL(v, base).href; } catch (e) { return v; }
  }

  function El(node, base) { this.n = node || rong(); this.base = base; }
  El.prototype = {
    select: function (q) { return new Els(chon(this.n, q), this.base); },
    text: function () { return gọn(this.n.textContent); },
    html: function () { return this.n.innerHTML || ''; },
    outerHtml: function () { return this.n.outerHTML || ''; },
    attr: function (name) {
      if (name && name.indexOf('abs:') === 0) {
        return tuyetDoi(this.n.getAttribute(name.slice(4)) || '', this.base);
      }
      return this.n.getAttribute ? (this.n.getAttribute(name) || '') : '';
    },
    attributes: function () {
      var o = {};
      if (this.n.attributes) for (var i = 0; i < this.n.attributes.length; i++) {
        o[this.n.attributes[i].name] = this.n.attributes[i].value;
      }
      return o;
    },
    remove: function () { if (this.n.remove) this.n.remove(); },
    tagName: function (moi) {
      if (moi === undefined) return (this.n.tagName || '').toLowerCase();
      this.n = doiThe(this.n, moi);         // kieu Jsoup: tagName("span") = doi ten the
      return this;
    },
    parent: function () { return new El(this.n.parentElement, this.base); },
    children: function () { return new Els(Array.from(this.n.children || []), this.base); },
  };

  // thay <a>...</a> bang <span>...</span> giu nguyen con va thuoc tinh
  function doiThe(n, ten) {
    if (!n.ownerDocument) return n;
    var moi = n.ownerDocument.createElement(ten);
    while (n.firstChild) moi.appendChild(n.firstChild);
    if (n.attributes) for (var i = 0; i < n.attributes.length; i++) {
      moi.setAttribute(n.attributes[i].name, n.attributes[i].value);
    }
    if (n.parentNode) n.parentNode.replaceChild(moi, n);
    return moi;
  }

  function Els(arr, base) { this.a = arr || []; this.base = base; }
  Els.prototype = {
    select: function (q) {
      var out = [];
      for (var i = 0; i < this.a.length; i++) out = out.concat(chon(this.a[i], q));
      return new Els(out, this.base);
    },
    first: function () { return new El(this.a[0], this.base); },
    last: function () { return new El(this.a[this.a.length - 1], this.base); },
    get: function (i) { return new El(this.a[i], this.base); },
    size: function () { return this.a.length; },
    isEmpty: function () { return this.a.length === 0; },
    forEach: function (fn) { var b = this.base; this.a.forEach(function (n, i) { fn(new El(n, b), i); }); },
    map: function (fn) { var b = this.base; return this.a.map(function (n, i) { return fn(new El(n, b), i); }); },
    remove: function () { this.a.forEach(function (n) { if (n.remove) n.remove(); }); },
    text: function () { return this.a.map(function (n) { return gọn(n.textContent); }).join(' ').trim(); },
    html: function () { return this.a.length ? (this.a[0].innerHTML || '') : ''; },
    attr: function (name) { return this.a.length ? new El(this.a[0], this.base).attr(name) : ''; },
    tagName: function (moi) {
      if (moi === undefined) return this.a.length ? (this.a[0].tagName || '').toLowerCase() : '';
      this.a = this.a.map(function (n) { return doiThe(n, moi); });
      return this;
    },
  };

  var Html = {
    parse: function (html, base) {
      var doc = new DOMParser().parseFromString(String(html == null ? '' : html), 'text/html');
      return new El(doc.documentElement, base || '');
    },
  };

  async function vbFetch(url, opts) {
    opts = opts || {};
    var u = String(url);
    if (opts.queries) {
      var qs = new URLSearchParams();
      for (var k in opts.queries) qs.append(k, opts.queries[k]);
      u += (u.indexOf('?') >= 0 ? '&' : '?') + qs.toString();
    }
    var dich = PROXY ? PROXY + encodeURIComponent(u) : u;
    var headers = opts.headers || {};
    if (!headers['User-Agent'] && !headers['user-agent']) headers['User-Agent'] = UA;
    var r = await window.fetch(dich, {
      method: opts.method || 'GET',
      headers: headers,
      body: opts.body,
    });
    var buf = new Uint8Array(await r.arrayBuffer());
    var giai = function (cs) { try { return new TextDecoder(cs || 'utf-8').decode(buf); } catch (e) { return new TextDecoder().decode(buf); } };
    var cuoi = (!PROXY && r.url) ? r.url : u;      // qua proxy thi r.url la proxy
    return {
      status: r.status, statusText: r.statusText, ok: r.ok, url: cuoi,
      headers: (function () { var o = {}; r.headers.forEach(function (v, k) { o[k] = v; }); return o; })(),
      header: function (k) { return r.headers.get(k) || ''; },
      text: function (cs) { return giai(cs); },
      string: function (cs) { return giai(cs); },   // ten cu trong API doi dau
      json: function () { return JSON.parse(giai()); },
      html: function (cs) { return Html.parse(giai(cs), cuoi); },
      base64: function () { var s = ''; for (var i = 0; i < buf.length; i++) s += String.fromCharCode(buf[i]); return btoa(s); },
      request: { url: u, headers: headers },
    };
  }

  function khoRieng(extId, tienTo) {
    var goc = tienTo + extId + ':';
    return {
      setItem: function (k, v) { try { localStorage.setItem(goc + k, String(v)); } catch (e) { } },
      getItem: function (k) { try { return localStorage.getItem(goc + k); } catch (e) { return null; } },
      removeItem: function (k) { try { localStorage.removeItem(goc + k); } catch (e) { } },
      clear: function () { },
    };
  }

  function taoCtx(ext) {
    var ctx = {
      Response: {
        success: function (d, d2) { return { __vb: 1, ok: true, data: d, data2: d2 === undefined ? '' : d2 }; },
        error: function (m) { return { __vb: 1, ok: false, loi: String(m) }; },
      },
      Html: Html,
      fetch: vbFetch,
      Http: {   // API doi cu, mot so extension van dung
        get: function (u, o) { return vbFetch(u, o); },
        post: function (u, o) { o = o || {}; o.method = 'POST'; return vbFetch(u, o); },
      },
      sleep: function (ms) { return new Promise(function (r) { setTimeout(r, Number(ms) || 0); }); },
      console: console,
      Log: { log: function () { console.log.apply(console, ['[' + ext.id + ']'].concat([].slice.call(arguments))); } },
      localStorage: khoRieng(ext.id, 'vb-ls:'),
      cacheStorage: khoRieng(ext.id, 'vb-cs:'),
      localConfig: {
        getItem: function (k) {
          return (ext.config && ext.config[k] != null) ? String(ext.config[k]) : null;
        },
      },
      localCookie: { setCookie: function () { }, getCookie: function () { return ''; } },
      UserAgent: {
        system: function () { return UA; }, chrome: function () { return UA; },
        android: function () { return UA; }, ios: function () { return UA; },
      },
    };
    if (ext.config) {
      for (var k in ext.config) ctx['CONFIG_' + k.toUpperCase()] = String(ext.config[k]);
    }
    return ctx;
  }

  var biSoan = {};   // extId:script -> ham da bien dich

  async function chay(ext, script, args) {
    var code = ext.scripts[script];
    if (!code) throw new Error('nguồn ' + ext.id + ' không có ' + script);
    var key = ext.id + ':' + script;
    if (!biSoan[key]) {
      biSoan[key] = new Function('__ctx',
        'with(__ctx){' + code + '\n;return execute;}');
    }
    var execute = biSoan[key](taoCtx(ext));
    var kq = await execute.apply(null, args || []);
    if (!kq || kq.__vb !== 1) throw new Error('nguồn không trả lời (web đổi giao diện?)');
    if (!kq.ok) throw new Error(kq.loi || 'nguồn báo lỗi');
    return kq;
  }

  /* ---------- cai extension luc chay: chuyen ma sync -> async ---------- */
  // fetch(...).html() phai thanh (await fetch(...)).html() — boc dung dau
  // ngoac dong (dem ngoac, bo qua noi dung chuoi), nhu tools/dong_goi_nguon.py
  function bocAwait(code, mau) {
    var re = new RegExp('\\b' + mau + '\\s*\\(', 'g');
    var ra = [];
    var i = 0;
    var m;
    re.lastIndex = 0;
    while ((m = re.exec(code))) {
      if (m.index < i) continue;
      ra.push(code.slice(i, m.index));
      var j = re.lastIndex;
      var sau = 1;
      var trong = '';
      while (j < code.length && sau) {
        var c = code[j];
        if (trong) {
          if (c === '\\') j++;
          else if (c === trong) trong = '';
        } else if (c === "'" || c === '"' || c === '`') trong = c;
        else if (c === '(') sau++;
        else if (c === ')') sau--;
        j++;
      }
      ra.push('(await ' + code.slice(m.index, j) + ')');
      i = j;
      re.lastIndex = j;
    }
    ra.push(code.slice(i));
    return ra.join('');
  }

  function bienDoi(code) {
    code = code.replace(/\bfunction\s+execute\b/g, 'async function execute');
    ['fetch', 'sleep', 'Http\\s*\\.\\s*get', 'Http\\s*\\.\\s*post']
      .forEach(function (t) { code = bocAwait(code, t); });
    return code;
  }

  function inlineLoad(code, files, daVao) {
    daVao = daVao || {};
    return code.replace(/load\(\s*['"]([^'"]+)['"]\s*\)\s*;?/g, function (m, ten) {
      ten = ten.split('/').pop();
      if (daVao[ten]) return '';
      daVao[ten] = 1;
      return '\n' + inlineLoad(files[ten] || '', files, daVao) + '\n';
    });
  }

  var CAM = ['Engine.', 'WebSocket(', 'Graphics.', 'Qt.'];

  // unzipFn: ham giai nen cua app (nhan ArrayBuffer, tra {ten, doc})
  async function caiTuZip(buf, tenFile, unzipFn) {
    var z = await unzipFn(buf);
    var td = new TextDecoder();
    var pjRaw = await z.doc('plugin.json');
    if (!pjRaw) throw new Error('file không có plugin.json — không phải extension VBook');
    var pj = JSON.parse(td.decode(pjRaw));
    var meta = pj.metadata || {};
    if (meta.encrypt) throw new Error('extension này bị mã hoá, không cài được');

    var files = {};
    for (var i = 0; i < z.ten.length; i++) {
      var n = z.ten[i];
      if (n.slice(-3) === '.js') files[n.split('/').pop()] = td.decode(await z.doc(n));
    }
    for (var f in files) {
      for (var k = 0; k < CAM.length; k++) {
        if (files[f].indexOf(CAM[k]) >= 0) {
          throw new Error('extension dùng API chưa hỗ trợ (' + CAM[k] + ') trong ' + f);
        }
      }
    }
    var map = {};
    var sm = pj.script || {};
    for (var vaiTro in sm) map[vaiTro] = String(sm[vaiTro]).split('/').pop();
    var scripts = {};
    for (var fname in files) {
      if (fname !== 'config.js') scripts[fname] = bienDoi(inlineLoad(files[fname], files));
    }
    if (!scripts[map.search || 'search.js'] && !scripts[map.detail || 'detail.js']) {
      throw new Error('extension thiếu script search/detail');
    }
    var cfg = {};
    var pc = pj.config || {};
    for (var ck in pc) cfg[ck] = (pc[ck] && pc[ck]['default']) || '';
    var ten = meta.name || String(tenFile).replace(/\.zip$/i, '');
    var id = 'ext-' + ten.toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '')
      .replace(/đ/g, 'd').replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '');
    return {
      id: id, ten: ten, nguon: meta.source || '', regexp: meta.regexp || '',
      map: map, config: cfg, scripts: scripts, caiThem: true, them: Date.now(),
    };
  }

  return { chay: chay, Html: Html, fetch: vbFetch, tuyetDoi: tuyetDoi, caiTuZip: caiTuZip };
})();

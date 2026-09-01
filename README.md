# DCR - DragonCloud_reading

Tải truyện chữ về máy, xuất ra **EPUB** (đọc trên Kindle, Koreader, điện thoại) và **TXT**.

Chạy hoàn toàn trên máy bạn, không gửi gì ra ngoài ngoài chính trang truyện bạn chọn.

---

## Cài đặt (chạy 1 lần)

Bấm đúp **`CaiDat.bat`**. Nó cài thư viện cần thiết rồi tạo shortcut
**DCReading** ngoài Desktop và trong Menu Start.

Từ đó về sau chỉ cần **nhảy đúp shortcut trên Desktop** — ra thẳng cửa sổ app,
không cửa sổ đen, không phải đụng tới file `.bat` nào nữa.

Shortcut trỏ vào `pythonw.exe` (bản Python không kèm cửa sổ lệnh). Vì vậy khi
app lỗi thì không có chỗ nào hiện traceback — app sẽ tự ghi vào
`data\loi_khoi_dong.txt` và bật một hộp thoại báo lỗi.

---

## Chạy

Ba cách chạy:

| Lệnh | Kết quả |
|---|---|
| `python app.py` | Cửa sổ app riêng (mặc định) |
| `python app.py --web` | Mở trong trình duyệt — hoặc bấm `ChayTrenTrinhDuyet.bat` |
| `python app.py --url "..." --tu 1 --den 200` | Tải thẳng bằng dòng lệnh, không giao diện |

Bấm đúp `TaiBangLink.bat` cũng được — nó hỏi link rồi tải luôn.

Yêu cầu: Python 3.10+ và:

```bash
python -m pip install requests beautifulsoup4 lxml pywebview pymupdf qrcode
```

`pywebview` chỉ cần cho cửa sổ app; thiếu nó thì vẫn chạy được bằng `--web`.
Trên Windows nó dùng WebView2 có sẵn của hệ điều hành, tốn khoảng 450 MB RAM —
nhẹ hơn nhiều so với việc mở Chrome (thường 3 GB trở lên), nhưng vẫn là
Chromium nên đừng kỳ vọng xuống vài chục MB.

---

## Dùng thế nào

1. **Tìm truyện** — gõ tên truyện, hoặc **dán thẳng link trang truyện** rồi Enter.
2. Bấm vào truyện → hiện bìa, tác giả, số chương.
3. Chọn khoảng chương (hoặc *Toàn bộ* / *100 chương cuối*), tích EPUB/TXT → **Tải xuống**.
4. Tab **Đang tải** xem tiến độ.
5. Tab **Thư viện** — bấm vào truyện để mở **màn hình chọn chương**:
   - Danh sách toàn bộ chương đã tải, có ô lọc (gõ số chương hoặc tên chương).
   - **Đọc tiếp** quay lại đúng chương đang đọc dở, hoặc **Đọc từ đầu**.
   - **Cập nhật chương mới** — đọc lại trang nguồn, chỉ tải phần chương mới rồi
     đóng gói lại EPUB/TXT. Nếu danh sách chương ở nguồn đã bị đổi thứ tự so với
     lúc tải, app báo để bạn tải lại thay vì ghép nhầm nội dung.
   - **Thư mục** mở nơi chứa file, **Xoá** xoá cả truyện lẫn thư mục (có hỏi lại).

   Trong trình đọc: mục lục, chuyển chương bằng nút hoặc phím ← →. Nút **Aa** mở
   bảng chỉnh kiểu đọc: cỡ chữ, phông (có chân/không chân), giãn dòng, bề ngang,
   nền **Tối / Giấy / Đen**. App nhớ **đúng chỗ đang cuộn dở** của từng truyện —
   mở lại là về ngay đó, chân trang hiện % đã đọc của chương. Ở tab Thư viện có
   nút **▶ Đọc tiếp** mở thẳng cuốn đang đọc dở gần nhất.

Truyện lưu tại `Truyen\<Tên truyện>\`, kèm thư mục `chuong\` chứa từng chương dạng text.
**Tải dở bị đứt thì chạy lại là tải tiếp** — chương nào đã có sẽ được bỏ qua.

---

## Nhập tài liệu có sẵn trên máy

Không cần nguồn web: có sẵn **EPUB, TXT, DOCX, PDF, HTML hay Markdown** thì đưa
thẳng vào thư viện. Ở tab **Thư viện** bấm **＋ Nhập tài liệu** (hoặc kéo thả file
vào cửa sổ app). Trước khi nhập có thể bấm **Xem thử tách chương** để xem mục lục
sẽ ra sao. Sách nhập xong đọc trong app, lọc chữ, xuất lại EPUB/TXT y hệt truyện
tải về.

Cách tách chương của từng loại:

- **EPUB** giữ nguyên chương theo mục lục, kèm bìa, tác giả, giới thiệu. EPUB dồn
  cả sách vào một file duy nhất sẽ được tách lại theo tiêu đề h1/h2/h3.
- **TXT** tách theo các dòng `Chương N…`, `Hồi N`, `Phần N`, `Chapter N`, `第N章`…
  Tự đoán bảng mã (UTF-8, UTF-16, GB18030…).
- **DOCX** tách theo Heading/Outline của Word. Nhiều cấp tiêu đề (Phần > Chương)
  thì tách ở cấp có nhiều tiêu đề nhất, cấp trên thành tiền tố tên chương
  (`Phần I · Chương 3`). Không dùng Heading thì dò `Chương N…` như TXT.
- **PDF** tách theo mục lục (bookmark) của file; không có thì dò `Chương N…`.
  Cần thư viện PyMuPDF (`CaiDat.bat` đã cài sẵn; thiếu thì
  `python -m pip install pymupdf`). PDF ảnh scan không có chữ thì chịu (cần OCR).
- **HTML** tách theo h1/h2/h3; **Markdown** theo `#`/`##`/`###`.
- Không nhận ra chương nào thì tự chia mỗi phần vài trăm dòng.

**Gộp nhiều file thành một cuốn** — sách bị xé lẻ thành `phan1.txt`, `phan2.txt`…
thì chọn hết, tích *Gộp tất cả thành một cuốn*, sắp thứ tự bằng nút ↑ rồi nhập:
mỗi file thành một (chùm) chương theo đúng thứ tự.

---

## Đọc trên điện thoại

Vào **Cài đặt → Đọc trên điện thoại**, tích *Cho thiết bị khác trong cùng mạng
Wi-Fi truy cập*, bấm **Lưu cài đặt** rồi tắt mở lại app. Lần đầu Windows có thể
hỏi cho phép Python qua tường lửa — chọn **Allow** với mạng riêng (Private).

Sau đó phần Cài đặt hiện **mã QR + địa chỉ** (kiểu `http://192.168.x.x:8765`):
điện thoại cùng Wi-Fi quét mã là mở được toàn bộ thư viện. Trong Chrome trên
điện thoại chọn **Thêm vào màn hình chính** — từ đó bấm icon là vào thẳng như
một app đọc truyện. Vị trí đọc dở trên điện thoại và trên máy tính được nhớ
riêng từng thiết bị.

Chỉ thiết bị trong cùng mạng nhà vào được; tắt tuỳ chọn này thì app quay lại
chỉ chạy trên máy tính như cũ.

---

## DCReader — app đọc truyện riêng cho Android

Thư mục `mobile\` là một app đọc truyện **chạy độc lập trên điện thoại**:

- **Khám phá & tải truyện từ nguồn**: chọn nguồn (BLHVIP, TruyenFull, iSach…)
  để duyệt các mục Đề cử/Hot/Mới, tìm theo tên, hoặc **dán link BẤT KỲ trang
  truyện nào** — bộ dò tự đoán cấu trúc (đặc sản port từ bản PC: tự tìm khối
  danh sách chương, tự suy kiểu phân trang, tự đoán khung nội dung).
  «Đọc ngay» thì mỗi chương tự tải khi mở tới, «Tải cả truyện» thì cất hết vào
  máy để đọc offline; nút ⟳ trên thẻ truyện kiểm tra chương mới.
- **Quản lý nguồn ngay trong app** — bấm ⚙ cạnh dãy nguồn:
  công tắc bật/tắt từng nguồn, và **＋ Cài nguồn mới** từ file `plugin.zip`
  định dạng extension VBook (chọn file trong máy hoặc dán link .zip) — app tự
  chuyển mã và cài, không cần build lại; nút Xoá gỡ nguồn đã cài.
  Kho extension cộng đồng:
  [vbook-extensions](https://github.com/Darkrai9x/vbook-extensions) (GPL-3) —
  lưu ý nhiều extension đã lỗi thời vì web đổi giao diện, cài xong nên thử
  tìm/đọc một truyện xem nguồn còn sống không.
- Nguồn đóng gói sẵn trong APK: `mobile/vbook.js` là lớp giả lập môi trường
  extension VBook; `tools/dong_goi_nguon.py` chuyển mã sync→async và đóng vào
  `mobile/nguon-vbook.js` (sửa danh sách `CHON` rồi chạy lại khi muốn đổi bộ
  có sẵn; extension lỗi thời với site thì vá bằng `patch`).
- Nhập EPUB/TXT từ bộ nhớ máy (tự tách chương như bản PC).
- Thư viện có bìa + tiến độ; trình đọc chìm (chạm giữa màn hình để hiện/ẩn
  thanh công cụ), bảng Aa, nhớ đúng chỗ đọc dở.
- **Truyện đã tải nằm hẳn trong điện thoại, đọc không cần mạng, không cần
  máy tính bật.** (Chỉ lúc tìm/tải chương mới cần mạng.)

- Cài trên điện thoại: chép file **`DCReader.apk`** sang máy (Zalo/USB/Drive)
  rồi bấm vào cài (cho phép "cài từ nguồn không rõ" nếu máy hỏi).
- Sửa code trong `mobile\` xong muốn ra APK mới: chạy **`DongGoiAPK.ps1`**.
  Cần bộ công cụ ở `D:	oolndroid-build\` (JDK 21 + Android SDK) và Node.
  Vỏ APK nằm ở `apk\` (Capacitor).
- Cách nạp truyện gọn nhất: bản PC tải truyện / đóng tài liệu → xuất EPUB →
  chép sang điện thoại → mở DCReader bấm **＋ Nhập**.

---

## Cài đặt đáng chú ý

| Mục | Ý nghĩa |
|---|---|
| Số luồng tải cùng lúc | 4–8 là hợp lý. Cao quá dễ bị web chặn. |
| Nghỉ giữa 2 lần gọi | Tăng lên 1–2 giây nếu bị chặn giữa chừng. |
| Tách tập mỗi N chương | Truyện 2000 chương nên để 300–500 cho máy đọc sách đỡ ì. `0` = gộp một file. |
| Proxy | Dùng khi nhà mạng chặn web nguồn. |
| Tự phát hiện dòng rác | Dòng nào lặp lại ở hầu hết các chương (chân trang, lời quảng cáo) sẽ bị bỏ. |

**Bộ lọc chữ** cho phép xoá chuỗi cố định, xoá hẳn dòng khớp regex, và đổi tên nhân vật
(mỗi dòng dạng `tên cũ = tên mới`) — tiện cho truyện convert.

---

## Thêm nguồn mới

Mỗi nguồn là **một file `.py` trong `plugins\`**. App tự nạp lúc khởi động
(hoặc bấm *Nạp lại plugin* trong Cài đặt). Chỉ cần 4 hàm:

```python
from core.sources import Book, BookBrief, Chapter, Source

class TenWebSource(Source):
    id = "tenweb"
    name = "Tên Web"
    domains = ["tenweb.com"]      # để trống = nhận mọi trang chưa có plugin riêng
    priority = 20                 # số nhỏ = được ưu tiên chọn

    def search(self, keyword, page=1) -> list[BookBrief]: ...
    def fetch_book(self, url) -> Book: ...            # gán luôn book.chapters
    def fetch_content(self, chapter) -> str: ...      # trả HTML thô của chương
```

`self.http` đã lo sẵn retry, nghỉ giữa các lần gọi và đoán bảng mã:
`self.http.soup(url)`, `.text(url)`, `.bytes(url)`.

Có sẵn hai plugin:

- **`generic.py`** — xương sống của app, không cần viết gì thêm: cứ dán link là chạy.
  Tự đoán khung nội dung theo mật độ chữ, tự tìm khối danh sách chương theo tỷ lệ
  link chương trên tổng số link của khối, và tự suy ra kiểu đánh số trang để đọc
  hết các trang danh sách. Nó chỉ nhận link, không tìm theo tên được.
- **`blhvip.py`** — ví dụ cho trường hợp `generic.py` bó tay: trang nạp danh sách
  chương bằng JavaScript nên HTML ban đầu chỉ có đúng một link. Plugin gọi thẳng
  API của trang. Xem file này làm mẫu khi cần viết plugin cho web tương tự.

Dấu hiệu cần viết plugin riêng: dán link vào mà app báo chỉ thấy 0–1 chương.

---

## Cấu trúc

```
app.py              chạy giao diện web, hoặc tải thẳng bằng --url
core/net.py         HTTP: retry, giới hạn nhịp gọi theo domain, đoán encoding
core/sources.py     lớp Source + bộ nạp plugin
core/cleaner.py     HTML chương -> đoạn văn sạch, bộ lọc, dò dòng rác lặp lại
core/downloader.py  hàng đợi, tải song song, tải tiếp khi đứt, gọi xuất file
core/exporters.py   xuất EPUB (zipfile thuần) và TXT
core/importer.py    nhập EPUB/TXT/DOCX/PDF/HTML/MD có sẵn trên máy vào thư viện
core/store.py       cài đặt, bộ lọc, sổ thư viện
core/server.py      máy chủ nội bộ + API
plugins/            mỗi file một nguồn truyện
web/                giao diện
Truyen/             nơi truyện được lưu
```

---

## Lưu ý

Công cụ này chỉ tải về cho bạn đọc offline. Hãy tự cân nhắc bản quyền của truyện
và điều khoản của trang nguồn trước khi tải và chia sẻ lại.

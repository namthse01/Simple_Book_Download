# DCR - DragonCloud_reading

Tải truyện chữ về máy, xuất ra **EPUB** (đọc trên Kindle, Koreader, điện thoại) và **TXT**.

Chạy hoàn toàn trên máy bạn, không gửi gì ra ngoài ngoài chính trang truyện bạn chọn.

---

## Chạy

Bấm đúp **`ChayApp.bat`** → mở ra **cửa sổ app riêng**, không cần trình duyệt.

Ba cách chạy:

| Lệnh | Kết quả |
|---|---|
| `python app.py` | Cửa sổ app riêng (mặc định) |
| `python app.py --web` | Mở trong trình duyệt — hoặc bấm `ChayTrenTrinhDuyet.bat` |
| `python app.py --url "..." --tu 1 --den 200` | Tải thẳng bằng dòng lệnh, không giao diện |

Bấm đúp `TaiBangLink.bat` cũng được — nó hỏi link rồi tải luôn.

Yêu cầu: Python 3.10+ và:

```bash
python -m pip install requests beautifulsoup4 lxml pywebview
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
5. Tab **Thư viện** — mỗi truyện có 3 nút:
   - **Đọc** — đọc ngay trong app: có mục lục, chuyển chương bằng nút hoặc phím
     ← →, chỉnh cỡ chữ, đổi nền giấy/tối, và nhớ chương đang đọc dở của từng truyện.
   - **Thư mục** — mở thư mục chứa file EPUB/TXT.
   - **Xoá** — xoá truyện khỏi thư viện và xoá cả thư mục file (có hỏi lại trước).

Truyện lưu tại `Truyen\<Tên truyện>\`, kèm thư mục `chuong\` chứa từng chương dạng text.
**Tải dở bị đứt thì chạy lại là tải tiếp** — chương nào đã có sẽ được bỏ qua.

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

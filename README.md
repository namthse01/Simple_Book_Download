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

## ⚔ Thâm nhập thế giới — nhập vai vào truyện (bản PC)

Cạnh mỗi truyện trong **Thư viện** có nút **⚔ Thâm nhập**: tạo một nhân vật của
riêng bạn và **sống trong thế giới truyện** — mỗi hành động bạn gõ, AI (đóng vai
quản trò) viết tiếp một chương truyện mới cho riêng bạn.

**Cần một máy chủ AI nói chuẩn OpenAI.** Miễn phí và chạy hoàn toàn trên máy:
cài [Ollama](https://ollama.com) (nhớ để nó chạy — `ollama serve`), tải một model
viết tiếng Việt sạch như `ollama pull gemma3:12b`, xong vào **Cài đặt → Nhập vai
AI** bấm *Kiểm tra kết nối* rồi chọn model. Model họ qwen "suy nghĩ" trước khi
viết — app tự tắt suy nghĩ qua API riêng của Ollama, nhưng qwen tắt nghĩ hay chèn
lẫn chữ Hán vào văn Việt, nên họ gemma hợp việc này hơn. Muốn văn hay hơn nữa thì
điền dịch vụ trả phí (OpenAI, DeepSeek, Gemini…) — chỉ cần đổi địa chỉ + API key.

**Khởi tạo thế giới** (mỗi truyện làm **1 lần duy nhất** — về sau thế giới tự
tiến hoá theo những gì xảy ra khi chơi): AI đọc **toàn bộ chương đã tải** theo
từng lô, rồi kiến tạo "sổ tay thế giới" gồm 11 phần:

1. Tổng quan — thế giới, cốt truyện, quy luật ẩn, văn phong, dòng thời gian;
2. Lịch sử — thời đại, chiến tranh, văn minh, nguyên nhân → hậu quả;
3. Cấu trúc & bản đồ — quốc gia, thành phố, địa hình, **khoảng cách & liên kết**;
4. Thời gian & môi trường — ngày/đêm, mùa, thời tiết, động thực vật, quái vật,
   tài nguyên, sinh thái ảnh hưởng lẫn nhau;
5. Nhân vật — chính/phụ, tính cách, mục tiêu, ký ức, quan hệ, khả năng phát
   triển + quy tắc sinh NPC mới;
6. Phe phái & chính trị — quốc gia, tổ chức, tôn giáo, gia tộc, lợi ích, xung
   đột, quyền lực, ngoại giao, luật pháp;
7. Văn hoá & kinh tế — kiến trúc, trang phục, phong tục, ngôn ngữ, ẩm thực,
   tín ngưỡng, tiền tệ, giá cả, nghề nghiệp;
8. Quy luật thế giới — vật lý, ma pháp, năng lượng, linh dị, nhân quả, **cái
   chết & hồi sinh**;
9. Giới hạn & hệ thống sức mạnh — cấp độ, cách phát triển, ưu/nhược, giá phải
   trả, tương khắc, trần sức mạnh, điều tuyệt đối không thể phá vỡ;
10. Bí mật — lịch sử che giấu, tổ chức ngầm, di tích, chân tướng, kèm **ba tầng
    thông tin** (quản trò biết / nhân vật biết / chưa ai biết) và điều kiện hé lộ;
11. Khu vực & sự kiện — bố cục, NPC, hoạt động, tài nguyên, nguy hiểm + **bảng
    sự kiện theo độ hiếm** (phổ biến / không thường / hiếm / cực hiếm / **độc
    nhất** — chỉ xảy ra một lần), sự kiện hiếm có **điều kiện kích hoạt**.

Sổ tay dựng từ bản cũ (7 mục) chỉ cần bấm **Khởi tạo tiếp** — phần phân tích
chương được giữ nguyên, AI chỉ viết thêm các mục còn thiếu.

Truyện dài chạy khá lâu với model trên máy — cứ để chạy nền; **dừng giữa chừng
không mất gì**, bấm Khởi tạo lần nữa là chạy tiếp từ chỗ dừng. Truyện quá dài có
thể chọn chế độ **Nhanh** (lấy mẫu đều khắp truyện, tối đa ~60 lô). Nên ưu tiên
truyện **đã hoàn thành** — truyện đang ra sẽ có cảnh báo vì thế giới thiếu phần kết.

**Chơi:** tạo nhân vật (chỉ bắt buộc tên — bỏ trống phần nào AI tự lo phần đó),
AI viết chương mở đầu, từ đó bạn gõ hành động (hoặc bấm gợi ý) → ra chương mới
(mỗi chương 1000–2000 chữ). Quản trò AI chạy theo luật:

- **Nhân quả**: mỗi hành động có hậu quả trực tiếp và lâu dài. App giữ riêng một
  **sổ việc còn treo** — lời hứa, món nợ, hẹn ước, lời đe doạ, phục bút vừa cài —
  bơm vào mọi chương sau để thế giới nhớ mà đòi lại đúng lúc; giải quyết xong
  thì mối đó tự rời sổ;
- **Thế giới tự vận hành**: NPC, phe phái, kinh tế, chiến sự vẫn chuyển động
  ở nơi bạn không có mặt; NPC, tin đồn, nhiệm vụ mới sinh ra dần theo thời gian;
- **Biến động vĩnh viễn**: ai chết là chết, phe đổi chủ là đổi — mọi thay đổi
  lớn được ghi vào sổ biến động của phiên chơi và **ghi đè nguyên tác**, thế
  giới không bao giờ reset hay tự mâu thuẫn (dài quá AI tự dồn sổ lại);
- **Ưu tiên khi xung đột**: lore gốc + biến động → quy luật thế giới → logic
  NPC → mong muốn người chơi → ngẫu nhiên;
- **Bất ngờ**: chương nào cũng cài ít nhất một biến số nhỏ không đoán trước.

Màn chơi bày như một trình đọc truyện: **danh sách chương nằm cột trái**, mỗi lần
chỉ hiện **một chương** chiếm trọn khổ giữa — đọc xong bấm *Chương sau →* hoặc
phím ← →, không phải cuộn qua cả mớ chương dính liền nhau. Đang xem lại chương cũ
thì có nút quay về chương mới nhất; ô hành động chỉ nhận khi bạn đứng ở hiện tại
của câu chuyện. Nút **Trạng thái** xem vị trí, thời gian, tu vi, vật phẩm, quan hệ
và sổ biến động thế giới. Mỗi nhân vật là một dòng thời gian riêng — chơi bao
nhiêu phiên tuỳ thích, thoát ra vào lại chơi tiếp được.

**Văn đọc như người viết:** quản trò được dạy bộ quy tắc văn phong thay vì để model
tự do — tả cảm xúc bằng hành động và chi tiết cảm quan thay vì tuyên bố thẳng
("anh cảm thấy buồn"), nhịp câu dài ngắn xen kẽ, đối thoại có ngắt lời và ẩn ý,
động từ mạnh thay trạng từ, chặn thẳng các câu sáo AI hay viết ("một cảm giác khó
tả", "mọi thứ sẽ không bao giờ như trước nữa"), cấm mở chương bằng tả thời tiết
và cấm kết chương bằng đúc kết triết lý. Trước khi viết, AI phác nhanh dàn cảnh
(chuyện gì xảy ra, cảm xúc chủ đạo, nhịp độ, chi tiết đắt) rồi mới viết — phần
nháp này bị cắt, bạn chỉ thấy chương hoàn chỉnh.

Muốn kỹ hơn nữa thì bật **Trau chuốt văn** trong Cài đặt: mỗi chương đi thêm một
lượt biên tập viên viết lại câu chữ, giữ nguyên 100% sự kiện và độ dài. Văn lên
rõ nhưng thời gian chờ gấp đôi.

**Đóng app là đóng hết.** Bấm ✕ (hoặc tắt kiểu gì đi nữa) thì máy chủ nội bộ
dừng, lượt tải đang dở dừng ngay, việc kiến tạo thế giới dừng, và **Ollama do app
tự bật cũng tắt theo** — không để thứ gì chạy ngầm ăn RAM. Ollama bạn tự mở trước
đó thì app không đụng vào. Việc đang dở không mất gì: tải tiếp và kiến tạo tiếp
đều chạy lại từ chỗ dừng.

**Tiện:** app tự bật Ollama nếu nó chưa chạy (chỉ với địa chỉ localhost) — bấm
Thâm nhập là chơi luôn, không phải mở gì trước. Ollama mặc định cửa sổ ngữ cảnh
khá ngắn nên app đặt `num_ctx` = 24576 cho đủ chứa sổ tay thế giới; máy ít VRAM
thấy chậm thì hạ trong **Cài đặt → Nhập vai AI**.

Dữ liệu nằm trong `Truyen\<Tên truyện>\the-gioi\` (sổ tay `world.json`, ghi chú
phân tích `phan-tich\`, các lần chơi `phien\`). Xoá thư mục này là truyện về lại
trạng thái chưa khởi tạo.

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
  Kết quả hiện dạng lưới bìa, **cuộn xuống là tự nạp trang tiếp** (cuộn vô tận).
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

## Đọc báo (tab **Đọc báo**)

Bấm **🔄 Cập nhật tin hôm nay** là app quét **141 nguồn RSS miễn phí của 9 nước**
(Việt Nam, Mỹ, Anh, Pháp, Trung Quốc, Nga, Nhật Bản, Brazil, Nam Phi) — khoảng
**2.600 tin trong ~45 giây** — rồi tự chia thành 9 mục: Thời sự · Chính trị ·
Quân sự · Kinh tế · Khoa học · Y tế · Thể thao · Văn hoá · Môi trường.

- **Đọc ngay trong app**: bấm vào tin là app lấy phần chữ + ảnh của bài đó về,
  bỏ hết script/quảng cáo/popup rồi hiển thị trong khung đọc sạch sẽ (kiểu
  "chế độ đọc" của trình duyệt). Chỉ lấy đúng bài bạn mở, không quét hàng loạt.
  Cuối bài luôn ghi tên báo và có nút **Mở trang báo** để sang bản gốc.
- **Dịch cả bài** sang **tiếng Việt / Trung / Anh** (chọn ở ô *Dịch sang*):
  mượn nguyên bộ máy của [Dịch Vạn Năng](../DichVanNang) — bộ nhớ dịch khớp
  100% → từ điển VietPhrase/HanViet (đường Trung→Việt) → AI Ollama đánh bóng.
  Bản dịch thay chữ tại chỗ, ảnh/video giữ nguyên, có nút **Xem bản gốc**.
  Kết quả được nhớ lại nên lần sau mở là hiện ngay.
- **Kho báo theo ngày**: mỗi lần cập nhật lưu vào `Truyen\Bao\<ngày>\` —
  `bao.json` cho app đọc lại, kèm một file `.txt` cho mỗi chủ đề để đọc/chia sẻ
  ngoài app. Chọn ngày ở ô **Ngày**, lọc theo **chủ đề**, theo **nước**, hoặc
  gõ từ khoá tìm trong ngày. Tin đã lưu thì đọc lại lúc nào cũng được.
- **⚙ Nguồn báo**: bật/tắt từng nguồn, lọc theo nước, và **thêm nguồn RSS mới**
  (có nút *Thử* để kiểm tra feed đọc được không trước khi thêm). Nguồn tự thêm
  xoá được; nguồn có sẵn tắt đi là thôi lấy tin.

Cần bật Ollama (`qwen3.5` hoặc model khác) để dịch các thứ tiếng ngoài
Trung→Việt; tắt Ollama thì phần Trung→Việt vẫn chạy bằng từ điển.

---

## Nhập tài liệu từ web (nút **🌐 Nhập từ web** ở tab Thư viện)

Dán địa chỉ trang có tài liệu (mỗi dòng một trang), app dò ra mọi file
**PDF · DOCX · EPUB · TXT · MD** trong đó, bạn tick cái nào thì tải cái đó rồi
nhập thẳng vào thư viện (vẫn đi qua bộ tách chương sẵn có, nên đọc được ngay
trong app và xuất được EPUB/TXT).

- **Dò sâu**: *chỉ trang này* · *thêm 1 lớp trang con* · *2 lớp*. Chỉ đi loanh
  quanh trong cùng tên miền, nhưng file tải về thì nhận cả link sang chỗ khác
  (CDN, GitHub Releases…).
- **Cư xử tử tế với máy chủ người ta**: đọc `robots.txt` trước, đường nào bị
  cấm thì bỏ qua; nghỉ giữa các lần gọi theo ô *Nghỉ giữa 2 lần gọi* trong Cài
  đặt; chặn số trang dò và số file mỗi lượt; file quá 80 MB thì bỏ.
- **Link không có đuôi file** kiểu *"Tải xuống (3.7 MB)"* hay `/download?id=…`
  vẫn nhận ra: app hỏi thẳng máy chủ (HEAD) xem đó là file gì rồi mới xếp vào.
- **Nhờ AI lọc giúp** (ô tick trong hộp): AI sẵn có của app đọc tên file + chữ
  trên link + tiêu đề trang, bỏ tick sẵn những thứ không phải tài liệu (README,
  LICENSE, CONTRIBUTING, mẫu đơn, file cấu hình) và **đặt tên dễ đọc** cho từng
  tài liệu — `AS1003_lecture-slides_chuong-4-bai-toan-gian.pdf` thành
  *"AS1003 Chương 4 Bài toán gian"*, vẫn giữ chi tiết phân biệt như mã đề, học kỳ.
  Tên file gốc hiện ngay dưới để đối chiếu. Cần chọn model ở tab Cài đặt.

**Theo dõi nguồn để lấy tài liệu mới.** Lúc nhập, để nguyên ô *Theo dõi trang
này* là app ghi trang đó vào sổ, kèm danh sách file đã lấy. Về sau mở lại hộp
*Nhập từ web* rồi bấm **Kiểm tra tài liệu mới** — app dò lại đúng những trang
đó và **chỉ hiện file chưa từng nhập**, không bày lại đống cũ. Mỗi nguồn trong
sổ có nút kiểm tra riêng và nút xoá; chỗ đó cũng ghi đã lấy bao nhiêu file và
kiểm tra lần cuối lúc nào.

Việc đối chiếu làm theo **địa chỉ file**, nên trang đổi giao diện hay đổi tên
hiển thị vẫn nhận ra đúng. Ngược lại, nếu bên họ đăng lại cùng một tài liệu ở
địa chỉ mới thì app coi là tài liệu mới — nhìn tên là biết, bỏ tick là xong.
App không tự dò nền; chỉ dò khi bạn bấm, để không làm phiền máy chủ người ta.

Ví dụ đã chạy: [BK Study Library](https://bk-study-library.github.io/hcmut-library/)
— tài liệu học tập sinh viên Bách Khoa TP.HCM chia sẻ, giấy phép CC-BY-SA-4.0;
dò 8 trang môn ra 21 file, nhập được 19 tài liệu (slide bài giảng, đề thi cũ,
tóm tắt, bảng công thức).

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

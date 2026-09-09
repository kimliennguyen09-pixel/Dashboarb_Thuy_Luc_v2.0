# GeoAI Hydraulic Dashboard

Ứng dụng web phân tích kết quả nút/hố ga xuất từ SewerGEMS. Backend Flask đọc dữ liệu CSV, chuẩn hóa trường thủy lực, tính các chỉ số dẫn xuất, phân loại cảnh báo và cung cấp REST API cho giao diện dashboard.

## 1. Ý nghĩa dữ liệu

Nguồn dữ liệu chính: `data/Bang thong ke.csv` gồm 139 nút/hố ga.

| Nhóm dữ liệu | Trường tiêu biểu | Ý nghĩa |
|---|---|---|
| Nhận dạng | `ID`, `Label` | Mã và tên nút trong mô hình |
| Cao độ | `Elevation (Ground/Rim/Invert)` | Cao độ mặt đất, nắp và đáy nút |
| Lưu lượng | `Flow (Total In/Out)` | Tổng lưu lượng vào và ra, đơn vị L/s |
| Chiều sâu | `Depth (Out/Flooding/Surcharged)` | Chiều sâu dòng chảy, ngập và quá tải |
| Đường năng lượng | `Hydraulic Grade Line (In/Out)` | Mực nước thủy lực tại đầu vào/đầu ra |
| Trạng thái | `Is Overflowing?` | Cho biết nút có tràn hay không |

Các chỉ số do ứng dụng tính thêm:

- `Available Depth (m) = Elevation Rim − Elevation Invert`;
- `HGL Margin (m) = Elevation Rim − max(HGL In, HGL Out)`;
- `Fill Ratio (%) = Depth Out / Available Depth × 100`;
- `Flood Level`: None, Low, Moderate, High hoặc Very High;
- `Risk`: Normal, Warning hoặc Critical;
- `Warning Reasons`: giải thích nguyên nhân cảnh báo.

Quy tắc cảnh báo:

- **Critical:** có tràn, có chiều sâu ngập hoặc HGL bằng/vượt cao độ nắp;
- **Warning:** biên HGL dưới 0,50 m hoặc tỷ lệ đầy từ 75%;
- **Normal:** không thuộc hai nhóm trên.

## 2. Kiến trúc sản phẩm

```text
SewerGEMS CSV
     ↓
Data processing trong api.py
     ↓
Flask REST API + Flask-CORS
     ↓ JSON
HTML/CSS/JavaScript Dashboard
     ↓
KPI · biểu đồ · bộ lọc · bảng nút · xuất CSV
```

Các endpoint chính:

| Endpoint | Chức năng |
|---|---|
| `GET /api/health` | Kiểm tra dịch vụ và số bản ghi |
| `GET /api/summary` | KPI tổng hợp; hỗ trợ bộ lọc |
| `GET /api/nodes` | Danh sách nút; hỗ trợ bộ lọc |
| `GET /api/nodes/<id>` | Chi tiết một nút |
| `GET /api/charts` | Dữ liệu cho ba biểu đồ |
| `GET /api/charts/export.csv` | Tải CSV của biểu đồ theo bộ lọc hiện tại |
| `POST /api/data/upload` | Upload, kiểm tra và kích hoạt file dữ liệu CSV mới |

Query parameters được hỗ trợ:

| Tham số | Kiểu/giới hạn | Ví dụ |
|---|---|---|
| `risk` | `all`, `Critical`, `Warning`, `Normal` | `risk=Critical` |
| `q` | Chuỗi tối đa 100 ký tự | `q=208` |
| `min_flood_depth` | Số ≥ 0 | `min_flood_depth=0.3` |
| `max_flood_depth` | Số ≥ 0 | `max_flood_depth=0.5` |
| `limit` | Số nguyên 1–50 | `limit=12` |
| `chart` | Tên biểu đồ, chỉ dùng khi export | `chart=flood_depth` |

Ví dụ:

```text
/api/charts?risk=Critical&min_flood_depth=0.3&limit=10
/api/charts/export.csv?chart=flood_depth&risk=Critical&limit=10
```

Input sai trả HTTP `400` với JSON gồm `error` và `message`. API có CORS header; mặc định cho phép mọi origin. Trong production nên đặt `CORS_ORIGINS` bằng danh sách domain được phép, phân cách bằng dấu phẩy.

Giao diện mục **Phân tích** có bộ lọc riêng theo ID/nhãn, trạng thái, khoảng chiều sâu ngập và số lượng Top N. Mỗi biểu đồ có nút **CSV**; nếu không có kết quả, biểu đồ hiển thị empty state thay vì vùng trống.

### Upload CSV

Tại mục **Báo cáo**, chọn file CSV và nhấn **Upload CSV**. API giới hạn file 5 MB và tối đa 10.000 dòng; kiểm tra đủ cột, kiểu số, ID trùng và giá trị `Is Overflowing?`. File chỉ thay thế dữ liệu hiện hành sau khi toàn bộ kiểm tra đạt; bản trước được lưu tại `data/Bang thong ke.backup.csv`.

## 3. Cấu trúc thư mục

```text
Hydraulic_Ngrok/
├── api.py
├── requirements.txt
├── run_with_ngrok.py
├── setup_ngrok.ps1
├── data/Bang thong ke.csv
├── templates/
│   ├── index.html
│   └── node-detail.html
├── static/
│   ├── css/
│   └── js/
└── tests/test_api.py
```

## 4. Cài đặt và chạy local trên Windows

Yêu cầu: Python 3.11 trở lên và PowerShell.

```powershell
cd Hydraulic_Ngrok
py -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python api.py
```

Mở `http://127.0.0.1:8000`; kiểm tra API tại `http://127.0.0.1:8000/api/health`.

Nếu PowerShell chặn kích hoạt môi trường ảo:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
.venv\Scripts\Activate.ps1
```

## 5. Chạy với ngrok

Không ghi token trực tiếp vào mã nguồn hoặc GitHub. Lấy token từ tài khoản ngrok rồi chạy:

```powershell
.\setup_ngrok.ps1 -Token "YOUR_NGROK_AUTHTOKEN"
```

Hoặc:

```powershell
$env:NGROK_AUTHTOKEN="YOUR_NGROK_AUTHTOKEN"
python run_with_ngrok.py
```

Terminal sẽ hiển thị URL công khai dạng `https://sermon-strict-handbag.ngrok-free.dev. Phải giữ terminal và máy tính hoạt động trong thời gian sử dụng tunnel.

## 6. Chạy kiểm thử

```powershell
python -m unittest discover -s tests -v
```

Bộ test kiểm tra dữ liệu, chỉ số dẫn xuất, CORS, input validation, empty data và xuất CSV.

## 7. Deploy lên Render

Đưa toàn bộ thư mục dự án lên GitHub, sau đó tạo Web Service trên Render:

| Mục | Giá trị |
|---|---|
| Runtime | Python 3 |
| Build Command | `pip install -r requirements.txt` |
| Start Command | `gunicorn api:app` |
| Health Check Path | `/api/health` |

Environment variable đề xuất:

```text
CORS_ORIGINS=https://your-frontend-domain.com
```

Nếu frontend và Flask cùng một domain, có thể giữ mặc định. Render tự cung cấp biến `PORT`; ứng dụng đã hỗ trợ biến này.

## 8. Thư viện trong requirements.txt

| Thư viện | Phiên bản | Vai trò |
|---|---:|---|
| Flask | 3.1.3 | Web framework và REST routes |
| Flask-Cors | 6.0.5 | CORS headers cho `/api/*` |
| Werkzeug | 3.1.6 | HTTP exceptions và WSGI utilities |
| gunicorn | 26.2.0 | Production server trên Render/Linux |
| pyngrok | 8.1.2 | Tunnel công khai từ máy cá nhân |
| Jinja2 | 3.1.6 | Render HTML templates |
| MarkupSafe | 3.0.3 | Escape dữ liệu trong templates |
| click | 8.5.0 | Command-line utilities của Flask |
| itsdangerous | 2.2.0 | Ký dữ liệu an toàn cho Flask |
| blinker | 1.9.0 | Signal support của Flask |
| packaging | 25.0 | Xử lý thông tin phiên bản/package |
| PyYAML | 6.0.3 | Cấu hình được pyngrok sử dụng |

Các thư viện trực tiếp và phụ thuộc runtime đều được khóa phiên bản để việc cài đặt có thể tái lập.
